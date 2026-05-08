"""Chat UI + JSON API that proxies to the local LLM."""
import functools
import json
import logging
import re
from datetime import timedelta

log = logging.getLogger("chat.views")

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts.activity import log_event
from accounts.models import ActivityEvent, ApiKey, UserProfile
from accounts import tiers as tier_lib

from . import llm as llm_backend
from .assistant import classify_prompt, explain_code
from .fallback import pick_fallback
from .naming import infer_chat_title
from .models import Conversation, Message


# Inline marker prepended to assistant Message.content so reloads can rebuild
# the same intro / summary / usage / suggestions wrapper without a DB schema
# change. The frontend strips the marker before rendering the body.
META_MARK_OPEN  = "<!-- DP_META: "
META_MARK_CLOSE = " -->\n"


def _wrap_with_meta(meta: dict, body: str) -> str:
    """Prepend a JSON meta block to a Message body."""
    if not meta:
        return body
    try:
        encoded = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return body
    return f"{META_MARK_OPEN}{encoded}{META_MARK_CLOSE}{body}"


def _user_tier_limits(user):
    """Resolve the user's effective tier limits dict. Free SNIFFER as fallback."""
    profile = getattr(user, "profile", None)
    slug = (profile.subscription_tier if profile else "sniffer") or "sniffer"
    return tier_lib.get_tier(slug), slug


def _monthly_generation_count(user):
    """Count this user's user-role messages in the rolling current month."""
    from django.utils import timezone as _tz
    now = _tz.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        Message.objects
        .filter(
            conversation__user=user,
            role=Message.USER,
            created_at__gte=month_start,
        )
        .count()
    )


def _resolve_api_key(request):
    """Return (user, key) for valid Bearer/X-Api-Key header, or (None, None)."""
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    raw = ""
    if auth.lower().startswith("bearer "):
        raw = auth.split(None, 1)[1].strip()
    if not raw:
        raw = request.META.get("HTTP_X_API_KEY", "").strip()
    if not raw:
        return (None, None)
    key = ApiKey.lookup(raw)
    if key is None:
        return (None, None)
    # Touch last_used; cheap update.
    from django.utils import timezone as _tz
    key.last_used = _tz.now()
    key.save(update_fields=["last_used"])
    return (key.user, key)


def login_or_api_key(view):
    """Allow either a session-authenticated user OR a valid API key.

    Wraps the view with @csrf_exempt so API-key clients don't need a CSRF token;
    when falling back to the session-auth path, CSRF is enforced manually.
    """
    @csrf_exempt
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        api_user, _ = _resolve_api_key(request)
        if api_user is not None:
            request.user = api_user
            return view(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return JsonResponse({"error": "auth_required"}, status=401)
        profile = getattr(request.user, "profile", None)
        if profile is not None and not profile.email_verified:
            return JsonResponse({"error": "email_unverified"}, status=403)
        # Session-authenticated browser path — enforce CSRF since we're csrf_exempt.
        from django.middleware.csrf import CsrfViewMiddleware
        mw = CsrfViewMiddleware(lambda r: None)
        check = mw.process_view(request, None, (), {})
        if check is not None:
            return JsonResponse({"error": "csrf_failed"}, status=403)
        return view(request, *args, **kwargs)
    return wrapper


def _cors_allowed_origin(request_origin):
    """Return the allowed origin string to echo back, or None if not allowed."""
    if not request_origin:
        return None
    allowed = getattr(settings, "LLM_CORS_ALLOW_ORIGINS", []) or []
    if "*" in allowed:
        return "*"
    if request_origin in allowed:
        return request_origin
    return None


def cors_for_api(view):
    """Add CORS preflight + response headers to a JSON API view.

    Browser-based third-party apps can hit /api/chat/ with a Bearer API key.
    Without these headers their preflight request fails."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        origin = request.META.get("HTTP_ORIGIN", "")
        allowed = _cors_allowed_origin(origin)

        if request.method == "OPTIONS":
            from django.http import HttpResponse
            response = HttpResponse(status=204 if allowed else 403)
            if allowed:
                response["Access-Control-Allow-Origin"]  = allowed
                response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
                requested = request.META.get("HTTP_ACCESS_CONTROL_REQUEST_HEADERS", "")
                response["Access-Control-Allow-Headers"] = (
                    requested or "Authorization, Content-Type, X-Api-Key, X-CSRFToken"
                )
                response["Access-Control-Max-Age"] = "600"
                response["Vary"] = "Origin"
            return response

        response = view(request, *args, **kwargs)
        if allowed:
            response["Access-Control-Allow-Origin"] = allowed
            response["Vary"] = "Origin"
        return response
    return wrapper


def _bucket_conversations(conversations):
    """Group conversations into Pinned + Today / Yesterday / 7d / 30d / Earlier.

    Pinned conversations always appear in their own sticky group at the top
    (in -updated_at order); they are excluded from the date buckets below
    so they don't show up twice.
    """
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    week_cutoff  = today - timedelta(days=7)
    month_cutoff = today - timedelta(days=30)

    pinned = [c for c in conversations if c.is_pinned]
    buckets = [
        ("Pinned",        pinned),
        ("Today",         []),
        ("Yesterday",     []),
        ("Last 7 days",   []),
        ("Last 30 days",  []),
        ("Earlier",       []),
    ]
    for c in conversations:
        if c.is_pinned:
            continue
        d = timezone.localtime(c.updated_at).date()
        if d >= today:           buckets[1][1].append(c)
        elif d >= yesterday:     buckets[2][1].append(c)
        elif d >= week_cutoff:   buckets[3][1].append(c)
        elif d >= month_cutoff:  buckets[4][1].append(c)
        else:                    buckets[5][1].append(c)
    return [b for b in buckets if b[1]]


@login_required
def chat_page(request):
    profile = getattr(request.user, "profile", None)
    if profile is not None and not profile.email_verified:
        from django.shortcuts import redirect as _redirect
        return _redirect("accounts:verify_pending")
    conversations = list(
        Conversation.objects.filter(user=request.user).order_by("-updated_at")
    )
    active_id = request.GET.get("c")
    active = None
    if active_id:
        active = Conversation.objects.filter(id=active_id, user=request.user).first()
    if active is None and conversations:
        active = conversations[0]
    messages = list(active.messages.all()) if active else []
    if active:
        prompt_tot, comp_tot, cost = _conversation_totals(active)
        totals = {
            "prompt_tokens": prompt_tot,
            "completion_tokens": comp_tot,
            "total_tokens": prompt_tot + comp_tot,
            "cost_usd": round(cost, 4),
        }
    else:
        totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    return render(request, "chat/chat.html", {
        "conversations": conversations,
        "conversation_buckets": _bucket_conversations(conversations),
        "active_conversation": active,
        "active_messages": messages,
        "session_totals": totals,
        "language_c_available": llm_backend.is_language_available(Conversation.LANG_C),
    })


def _summarise(prompt: str, limit: int = 60) -> str:
    one_line = " ".join(prompt.strip().split())
    if len(one_line) <= limit:
        return one_line or "New chat"
    return one_line[: limit - 1].rstrip() + "…"


def _estimate_tokens(text: str) -> int:
    """Rough English/code estimator: ~4 chars per token. Returns at least 1
    for any non-empty text so we never report 0 for a real message."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _conversation_totals(conversation):
    """Sum prompt + completion tokens across the conversation. Returns
    (prompt, completion, cost_in_dollars)."""
    prompt_total = 0
    completion_total = 0
    for m in conversation.messages.all():
        if m.prompt_tokens:
            prompt_total += m.prompt_tokens
        if m.completion_tokens:
            completion_total += m.completion_tokens
    rate = float(getattr(settings, "LLM_COST_PER_1K_TOKENS", 0.0005))
    cost = (prompt_total + completion_total) * rate / 1000.0
    return (prompt_total, completion_total, cost)


@cors_for_api
@login_or_api_key
@require_http_methods(["POST", "OPTIONS"])
def api_chat(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    instruction = (payload.get("instruction") or "").strip()
    if not instruction:
        return JsonResponse({"error": "empty_prompt"}, status=400)

    try:
        temperature = float(payload.get("temperature", 0.7))
    except (TypeError, ValueError):
        temperature = 0.7
    temperature = max(0.0, min(2.0, temperature))

    try:
        max_tokens = int(payload.get("max_tokens", 2048))
    except (TypeError, ValueError):
        max_tokens = 2048
    max_tokens = max(16, min(8192, max_tokens))

    # ----- Tier caps (enforced on every dispatch) ----------------------
    tier, tier_slug = _user_tier_limits(request.user)
    # 1. Token budget per request
    tier_max = tier.get("max_tokens", 1024)
    if max_tokens > tier_max:
        max_tokens = tier_max  # silently clamp; UI surfaces the cap separately
    # 2. Monthly generation cap
    monthly_cap = tier.get("monthly_gens")
    if monthly_cap is not None:
        used = _monthly_generation_count(request.user)
        if used >= monthly_cap:
            return JsonResponse({
                "error":  "tier_quota_exceeded",
                "detail": (
                    f"Your {tier['name']} tier is capped at {monthly_cap} generations "
                    "per calendar month and you've used them all. Upgrade to continue."
                ),
                "tier":          tier_slug,
                "monthly_cap":   monthly_cap,
                "monthly_used":  used,
            }, status=429)

    # ----- Language gate: existing conversation always wins; new conv reads
    # the requested language from the payload (default asm). -----
    requested_lang = (payload.get("language") or Conversation.LANG_ASM).lower()
    if requested_lang not in {Conversation.LANG_ASM, Conversation.LANG_C}:
        requested_lang = Conversation.LANG_ASM
    # 3. Language access (free tier is ASM-only)
    allowed_langs = tier.get("languages") or {Conversation.LANG_ASM}
    if requested_lang not in allowed_langs:
        return JsonResponse({
            "error": "tier_language_locked",
            "detail": (
                f"The {requested_lang.upper()} model is restricted to higher tiers. "
                f"Your current tier ({tier['name']}) supports: "
                f"{', '.join(sorted(s.upper() for s in allowed_langs))}."
            ),
            "tier":           tier_slug,
            "allowed_langs":  sorted(allowed_langs),
        }, status=403)

    conversation_id = payload.get("conversation_id")
    if conversation_id:
        conversation = get_object_or_404(
            Conversation, id=conversation_id, user=request.user
        )
        # Refuse cross-language requests on an existing conversation.
        if requested_lang and requested_lang != conversation.language:
            return JsonResponse({
                "error": "language_mismatch",
                "detail": (
                    f"This conversation is locked to {conversation.language!r}. "
                    f"Start a new chat to use {requested_lang!r}."
                ),
            }, status=409)
        active_lang = conversation.language
    else:
        active_lang = requested_lang
        # No is_language_available() guard here — if the live C backend is
        # offline, the fallback corpus handler in the except block below
        # will serve a curated sample instead.
        conversation = Conversation.objects.create(
            user=request.user,
            title=_summarise(instruction),
            language=active_lang,
        )

    user_msg = Message.objects.create(
        conversation=conversation,
        role=Message.USER,
        content=instruction,
        temperature=temperature,
        max_tokens=max_tokens,
        prompt_tokens=_estimate_tokens(instruction),
    )

    # ----- Intent classification (Groq-powered, with local heuristic) -----
    # If the user said "hi" or asked "what can you do" we don't waste a Gradio
    # call — we hand back a friendly chat reply + clickable example prompts.
    intent = classify_prompt(instruction, lang=active_lang)
    if intent.get("kind") == "chat":
        meta = {
            "kind":        "chat",
            "suggestions": intent.get("suggestions") or [],
        }
        body = (intent.get("response") or "").strip() or "I'm Dark Prompt. Ask me to generate something."
        assistant_msg = Message.objects.create(
            conversation=conversation,
            role=Message.ASSISTANT,
            content=_wrap_with_meta(meta, body),
            temperature=temperature,
            max_tokens=max_tokens,
            completion_tokens=_estimate_tokens(body),
        )
        # First-exchange title nicety still applies — but for chat-only flows
        # the prompt is usually a greeting, so skip Groq title inference and
        # leave the auto-summarise title in place.
        conversation.save(update_fields=["updated_at"])

        p, c, cost = _conversation_totals(conversation)
        return JsonResponse({
            "conversation": {
                "id":       conversation.id,
                "title":    conversation.title,
                "language": conversation.language,
            },
            "user_message": {
                "id":            user_msg.id,
                "role":          "user",
                "content":       user_msg.content,
                "created_at":    user_msg.created_at.isoformat(),
                "prompt_tokens": user_msg.prompt_tokens,
            },
            "assistant_message": {
                "id":          assistant_msg.id,
                "role":        "assistant",
                "kind":        "chat",
                "content":     body,
                "suggestions": meta["suggestions"],
                "created_at":  assistant_msg.created_at.isoformat(),
                "completion_tokens": assistant_msg.completion_tokens,
            },
            "session_totals": {
                "prompt_tokens":     p,
                "completion_tokens": c,
                "total_tokens":      p + c,
                "cost_usd":          round(cost, 4),
            },
        })

    fallback_source = None  # filename of the offline-corpus sample, if used
    try:
        generated = llm_backend.generate(
            instruction,
            max_tokens=max_tokens,
            temperature=temperature,
            language=active_lang,
        )
        # The Gradio path doesn't return token counts, so leave `data` empty;
        # the estimator below fills in prompt_tokens / completion_tokens.
        data = {}
    except (
        llm_backend.LLMUnreachable,
        llm_backend.LLMTimeout,
        llm_backend.LLMBadResponse,
        llm_backend.LLMError,
    ) as exc:
        # The live model is down — try the offline corpus instead of erroring out.
        # If the corpus is empty / unreadable we still surface the original error.
        fb = pick_fallback(instruction, active_lang)
        if fb is None:
            error_map = {
                llm_backend.LLMUnreachable:  ("llm_unreachable", 502, f"Could not reach LLM backend at {settings.LLM_API_URL}."),
                llm_backend.LLMTimeout:      ("llm_timeout",     504, "LLM backend timed out."),
                llm_backend.LLMBadResponse:  ("llm_bad_response", 502, "LLM returned non-JSON output."),
                llm_backend.LLMError:        ("llm_error",        502, ""),
            }
            code, status_code, default_detail = error_map.get(
                type(exc), ("llm_error", 502, "")
            )
            return JsonResponse({
                "error":  code,
                "detail": getattr(exc, "detail", "") or default_detail,
                "conversation_id": conversation.id,
                "user_message_id": user_msg.id,
            }, status=status_code)
        fallback_source, generated = fb
        data = {}
        log.info(
            "LLM unreachable (%s) — served fallback %s (lang=%s)",
            type(exc).__name__, fallback_source, active_lang,
        )

    # Prefer real counts from the LLM if it sent them; fall back to estimator.
    prompt_tokens = (
        data.get("prompt_tokens") if isinstance(data, dict) else None
    ) or user_msg.prompt_tokens or _estimate_tokens(instruction)
    completion_tokens = (
        data.get("completion_tokens") if isinstance(data, dict) else None
    ) or _estimate_tokens(generated)

    # Backfill the user-message prompt count if the LLM gave us a real number.
    if user_msg.prompt_tokens != prompt_tokens:
        user_msg.prompt_tokens = prompt_tokens
        user_msg.save(update_fields=["prompt_tokens"])

    # ----- Wrap the generation with a Groq-produced intro / summary / usage.
    # Best-effort: if Groq is down or unconfigured, we just store the bare code
    # and the frontend renders without the wrapper. -----
    explanation = explain_code(instruction, generated, lang=active_lang)
    if explanation:
        meta = {
            "kind":    "code",
            "intro":   explanation.get("intro", ""),
            "summary": explanation.get("summary", ""),
            "usage":   explanation.get("usage", ""),
        }
        stored_content = _wrap_with_meta(meta, generated)
    else:
        meta = None
        stored_content = generated

    assistant_msg = Message.objects.create(
        conversation=conversation,
        role=Message.ASSISTANT,
        content=stored_content,
        temperature=temperature,
        max_tokens=max_tokens,
        completion_tokens=completion_tokens,
    )

    # If this was the very first exchange in the conversation, ask Groq for
    # a nicer title. Falls back to the existing _summarise() value silently
    # if Groq is unconfigured / unreachable / returns garbage.
    is_first_exchange = conversation.messages.count() == 2
    if is_first_exchange:
        inferred = infer_chat_title(instruction)
        if inferred:
            conversation.title = inferred
            conversation.save(update_fields=["title", "updated_at"])
        elif (conversation.title or "").strip().lower() in {"", "new chat"}:
            # User created an empty "+ New chat" first; even without Groq
            # we want a better-than-default title.
            conversation.title = _summarise(instruction)
            conversation.save(update_fields=["title", "updated_at"])
        else:
            conversation.save(update_fields=["updated_at"])
    else:
        conversation.save(update_fields=["updated_at"])

    p, c, cost = _conversation_totals(conversation)
    return JsonResponse({
        "conversation": {
            "id": conversation.id,
            "title": conversation.title,
            "language": conversation.language,
        },
        "user_message": {
            "id": user_msg.id,
            "role": "user",
            "content": user_msg.content,
            "created_at": user_msg.created_at.isoformat(),
            "prompt_tokens": user_msg.prompt_tokens,
        },
        "assistant_message": {
            "id":          assistant_msg.id,
            "role":        "assistant",
            "kind":        "code",
            # `content` here is the BARE code (no marker) so the frontend's
            # existing code-block renderer just works. The marker is stored
            # in the DB so reloads still get the wrapper.
            "content":     generated,
            "intro":       (meta or {}).get("intro", ""),
            "summary":     (meta or {}).get("summary", ""),
            "usage":       (meta or {}).get("usage", ""),
            "created_at":  assistant_msg.created_at.isoformat(),
            "completion_tokens": assistant_msg.completion_tokens,
        },
        "session_totals": {
            "prompt_tokens": p,
            "completion_tokens": c,
            "total_tokens": p + c,
            "cost_usd": round(cost, 4),
        },
    })


@login_required
@require_http_methods(["POST"])
def api_new_conversation(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    lang = (payload.get("language") or Conversation.LANG_ASM).lower()
    if lang not in {Conversation.LANG_ASM, Conversation.LANG_C}:
        lang = Conversation.LANG_ASM
    convo = Conversation.objects.create(user=request.user, title="New chat", language=lang)
    return JsonResponse({"id": convo.id, "title": convo.title, "language": convo.language})


@login_required
@require_http_methods(["GET"])
def api_search_conversations(request):
    """Return conversations whose title OR message body matches `q`.

    Response: {"results": [{id, title, kind, snippet}]} where kind is
    "title" (matched on title) or "message" (matched in a message body),
    snippet is a small windowed excerpt around the match (message kind only).
    """
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    from django.db.models import Q
    qs = (
        Conversation.objects
        .filter(user=request.user)
        .filter(Q(title__icontains=q) | Q(messages__content__icontains=q))
        .distinct()
        .order_by("-updated_at")[:30]
    )

    def _snippet(text, needle, window=80):
        if not text:
            return ""
        lower = text.lower()
        idx = lower.find(needle.lower())
        if idx < 0:
            return text[: window * 2].strip()
        start = max(0, idx - window)
        end = min(len(text), idx + len(needle) + window)
        snippet = text[start:end].strip()
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(text) else ""
        # Collapse runs of whitespace for tidier display.
        snippet = " ".join(snippet.split())
        return f"{prefix}{snippet}{suffix}"

    results = []
    needle = q.lower()
    for convo in qs:
        if needle in (convo.title or "").lower():
            results.append({
                "id": convo.id,
                "title": convo.title,
                "kind": "title",
                "snippet": "",
            })
            continue
        m = (
            convo.messages
            .filter(content__icontains=q)
            .order_by("-created_at")
            .first()
        )
        results.append({
            "id": convo.id,
            "title": convo.title,
            "kind": "message",
            "snippet": _snippet(m.content if m else "", q),
        })

    return JsonResponse({"results": results, "query": q})


@login_required
@require_http_methods(["GET"])
def api_conversation_detail(request, pk):
    convo = get_object_or_404(Conversation, id=pk, user=request.user)
    msgs = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in convo.messages.all()
    ]
    return JsonResponse({
        "id": convo.id,
        "title": convo.title,
        "language": convo.language,
        "messages": msgs,
    })


@login_required
@require_http_methods(["POST"])
def api_delete_conversation(request, pk):
    convo = get_object_or_404(Conversation, id=pk, user=request.user)
    title = convo.title
    convo.delete()
    log_event(request, ActivityEvent.CONVERSATION_DELETE, detail=title)
    return JsonResponse({"ok": True})


@login_required
@require_http_methods(["POST"])
def api_set_conversation_language(request, pk):
    """Change a conversation's language *only if it has no messages yet*.

    Once a chat has any message in it the language is locked — the client
    must create a new conversation to switch. This endpoint exists so the
    toggle can flip an empty just-created chat without spawning a new row.
    """
    convo = get_object_or_404(Conversation, id=pk, user=request.user)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    new_lang = (payload.get("language") or "").lower()
    if new_lang not in {Conversation.LANG_ASM, Conversation.LANG_C}:
        return JsonResponse({"error": "invalid_language"}, status=400)
    if convo.messages.exists():
        return JsonResponse({
            "error": "language_locked",
            "detail": "Conversation already has messages — language is fixed.",
        }, status=409)
    convo.language = new_lang
    convo.save(update_fields=["language"])
    return JsonResponse({"id": convo.id, "language": convo.language})


@login_required
@require_http_methods(["POST"])
def api_pin_conversation(request, pk):
    convo = get_object_or_404(Conversation, id=pk, user=request.user)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    if "pinned" in payload:
        convo.is_pinned = bool(payload["pinned"])
    else:
        convo.is_pinned = not convo.is_pinned
    convo.save(update_fields=["is_pinned"])
    return JsonResponse({"id": convo.id, "is_pinned": convo.is_pinned})


@login_required
@require_http_methods(["POST"])
def api_rename_conversation(request, pk):
    convo = get_object_or_404(Conversation, id=pk, user=request.user)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    new_title = (payload.get("title") or "").strip()
    if not new_title:
        return JsonResponse({"error": "empty_title"}, status=400)
    if len(new_title) > 255:
        new_title = new_title[:255]
    convo.title = new_title
    convo.save(update_fields=["title", "updated_at"])
    log_event(request, ActivityEvent.CONVERSATION_RENAME, detail=new_title)
    return JsonResponse({"id": convo.id, "title": convo.title})


def _safe_filename(title: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_\-]+", "_", title.strip())[:60].strip("_")
    return base or "conversation"


@login_required
@require_http_methods(["GET"])
def api_export_conversation(request, pk):
    convo = get_object_or_404(Conversation, id=pk, user=request.user)
    fmt = (request.GET.get("format") or "md").lower()
    if fmt not in {"md", "txt"}:
        fmt = "md"

    lines = []
    if fmt == "md":
        lines.append(f"# {convo.title}")
        lines.append("")
        lines.append(f"_Exported {timezone.now().strftime('%Y-%m-%d %H:%M UTC')}_")
        lines.append("")
        for m in convo.messages.all():
            who = "You" if m.role == Message.USER else "Dark Prompt"
            ts  = m.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"## {who} · {ts}")
            lines.append("")
            lines.append(m.content)
            lines.append("")
            lines.append("---")
            lines.append("")
        body = "\n".join(lines)
        content_type = "text/markdown; charset=utf-8"
        ext = "md"
    else:
        lines.append(f"{convo.title}")
        lines.append(f"Exported {timezone.now().strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append("=" * 60)
        for m in convo.messages.all():
            who = "You" if m.role == Message.USER else "Dark Prompt"
            ts  = m.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append("")
            lines.append(f"[{who} · {ts}]")
            lines.append(m.content)
            lines.append("-" * 60)
        body = "\n".join(lines)
        content_type = "text/plain; charset=utf-8"
        ext = "txt"

    filename = f"{_safe_filename(convo.title)}.{ext}"
    response = HttpResponse(body, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    log_event(
        request, ActivityEvent.CONVERSATION_EXPORT,
        detail=f"{convo.title} · .{ext}",
    )
    return response


@login_required
@require_http_methods(["POST"])
def api_analyse_code(request):
    """Static analysis of a code block — never executes the code."""
    from . import sandbox
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)
    code = payload.get("code") or ""
    lang = payload.get("lang") or ""
    if not code.strip():
        return JsonResponse({"error": "empty_code"}, status=400)
    try:
        result = sandbox.analyse(code, lang)
    except sandbox.SandboxError as exc:
        return JsonResponse({"error": "sandbox_refused", "detail": str(exc)}, status=413)
    except Exception as exc:
        log.exception("analyse crashed for lang=%r", lang)
        return JsonResponse({"error": "analyse_error", "detail": str(exc)}, status=500)
    return JsonResponse(result.to_dict())


@login_required
@require_http_methods(["POST"])
def api_compile_code(request):
    """Compile-only execution. Writes a binary to runtime/builds/.
    Never *runs* the result; just returns the build artefact."""
    from . import sandbox
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)
    code = payload.get("code") or ""
    lang = payload.get("lang") or ""
    if not code.strip():
        return JsonResponse({"error": "empty_code"}, status=400)
    try:
        result = sandbox.compile_code(code, lang)
    except sandbox.SandboxError as exc:
        return JsonResponse({"error": "sandbox_refused", "detail": str(exc)}, status=413)
    payload_out = result.to_dict()
    # Rewrite the placeholder URL into a real /api/builds/<dir>/<file>/ path.
    if payload_out.get("download_url", "").startswith("__BUILD__/"):
        rel = payload_out["download_url"][len("__BUILD__/"):]
        payload_out["download_url"] = "/api/builds/" + rel
    return JsonResponse(payload_out)


@login_required
@require_http_methods(["GET"])
def api_build_artefact(request, build_name, file_name):
    """Stream a compile artefact back to the user. Strict path validation."""
    from django.http import FileResponse, Http404
    from . import sandbox
    target = sandbox.serve_build_artefact(build_name, file_name)
    if target is None:
        raise Http404("Build artefact not found.")
    response = FileResponse(open(target, "rb"), as_attachment=True, filename=target.name)
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_http_methods(["GET"])
def conversation_print_view(request, pk):
    """Print-optimised HTML view of a conversation. The browser's
    Ctrl+P / Save as PDF turns this into a properly-styled PDF that
    matches the Dark Prompt visual identity."""
    convo = get_object_or_404(Conversation, id=pk, user=request.user)
    msgs = list(convo.messages.all())
    log_event(
        request, ActivityEvent.CONVERSATION_EXPORT,
        detail=f"{convo.title} · pdf",
    )
    return render(request, "chat/conversation_print.html", {
        "conversation": convo,
        "messages": msgs,
        "now": timezone.now(),
    })


@login_required
@require_http_methods(["POST"])
def api_regenerate(request, pk):
    """Regenerate an assistant message — re-run the LLM with the prior user prompt."""
    assistant_msg = get_object_or_404(
        Message, id=pk, role=Message.ASSISTANT, conversation__user=request.user
    )
    convo = assistant_msg.conversation
    # Find the user prompt that produced it: the last user message before this assistant.
    prior_user = (
        convo.messages
        .filter(role=Message.USER, created_at__lte=assistant_msg.created_at)
        .order_by("-created_at", "-id")
        .first()
    )
    if prior_user is None:
        return JsonResponse({"error": "no_prior_prompt"}, status=400)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    try:
        temperature = float(payload.get("temperature", assistant_msg.temperature or 0.7))
    except (TypeError, ValueError):
        temperature = 0.7
    temperature = max(0.0, min(2.0, temperature))
    try:
        max_tokens = int(payload.get("max_tokens", assistant_msg.max_tokens or 2048))
    except (TypeError, ValueError):
        max_tokens = 2048
    max_tokens = max(16, min(8192, max_tokens))

    try:
        generated = llm_backend.generate(
            prior_user.content,
            max_tokens=max_tokens,
            temperature=temperature,
            language=convo.language,
        )
    except llm_backend.LLMUnreachable as exc:
        return JsonResponse({
            "error": "llm_unreachable",
            "detail": exc.detail or f"Could not reach LLM backend at {settings.LLM_API_URL}.",
        }, status=502)
    except llm_backend.LLMTimeout as exc:
        return JsonResponse({"error": "llm_timeout", "detail": exc.detail or "LLM backend timed out."}, status=504)
    except llm_backend.LLMBadResponse as exc:
        return JsonResponse({"error": "llm_bad_response", "detail": exc.detail or "LLM returned non-JSON output."}, status=502)
    except llm_backend.LLMError as exc:
        return JsonResponse({"error": "llm_error", "detail": exc.detail}, status=502)

    assistant_msg.content = generated
    assistant_msg.temperature = temperature
    assistant_msg.max_tokens = max_tokens
    assistant_msg.save(update_fields=["content", "temperature", "max_tokens"])
    convo.save(update_fields=["updated_at"])

    return JsonResponse({
        "assistant_message": {
            "id": assistant_msg.id,
            "role": "assistant",
            "content": assistant_msg.content,
            "created_at": assistant_msg.created_at.isoformat(),
        },
    })
