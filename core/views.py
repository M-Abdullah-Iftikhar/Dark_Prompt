import time

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone


def landing(request):
    return render(request, "core/landing.html")


def about(request):
    return render(request, "core/about.html")


def contact(request):
    return render(request, "core/contact.html")


def security(request):
    return render(request, "core/security.html")


CHANGELOG_RELEASES = [
    {
        "version": "0.5.0",
        "date":    "2026-05-07",
        "tag":     "// HARDENING",
        "headline": "Identity, telemetry, devices",
        "items": [
            ("added",   "Email verification gates the chat console behind a one-click link."),
            ("added",   "TOTP-based 2FA with QR pairing, backup codes, and a login challenge."),
            ("added",   "Personal API keys for /api/chat/ — Bearer-token auth, hashed at rest."),
            ("added",   "Active sessions list with per-device revoke."),
            ("added",   "Activity log of the last 50 audited account events."),
            ("added",   "Per-session token + cost meter in the chat header."),
            ("added",   "Status page that probes the local LLM every five seconds."),
        ],
    },
    {
        "version": "0.4.0",
        "date":    "2026-05-06",
        "tag":     "// CONTROL",
        "headline": "Sidebar polish",
        "items": [
            ("added",   "Pin / unpin conversations into a sticky group at the top."),
            ("added",   "Full-text search across message bodies, not only titles."),
            ("added",   "Rename conversations from the sidebar or the chat header."),
            ("added",   "Export conversations as Markdown or plain text."),
            ("added",   "Code-block copy buttons enhanced site-wide."),
            ("added",   "Global keyboard shortcuts + ? cheat-sheet modal."),
        ],
    },
    {
        "version": "0.3.0",
        "date":    "2026-05-05",
        "tag":     "// FOUNDATION",
        "headline": "Auth and gates",
        "items": [
            ("added",   "Real password reset flow (signed token + email)."),
            ("added",   "Rate limiting on signup, login, forgot-password, and TOTP challenge."),
            ("added",   "Subscription tiers (SNIFFER / EXPLOIT / ZERO DAY) with ethical-use gating."),
            ("added",   "AUP confirmation checkbox on signup."),
            ("added",   "Settings page — edit profile, change password."),
            ("added",   "Custom 404 + 500 error pages with /404-preview/ and /500-preview/ routes."),
        ],
    },
    {
        "version": "0.2.0",
        "date":    "2026-05-04",
        "tag":     "// THEME",
        "headline": "Dark, locked in",
        "items": [
            ("changed", "Single theme — Dark — replaces the rotating theme picker."),
            ("added",   "Avatar dropdown menu with Settings + Sign out."),
            ("added",   "Chamfered chevron buttons across the chat console."),
            ("added",   "Logo image system replacing the ◢◤ glyph."),
            ("removed", "Cursor-follow magnetic button hover."),
        ],
    },
    {
        "version": "0.1.0",
        "date":    "2026-05-01",
        "tag":     "// ORIGIN",
        "headline": "First light",
        "items": [
            ("added",   "Local-LLM-backed chat console with streaming responses."),
            ("added",   "Account signup / login / logout with email-or-username auth."),
            ("added",   "Conversation history with delete + per-message regenerate."),
        ],
    },
]


def changelog(request):
    return render(request, "core/changelog.html", {"releases": CHANGELOG_RELEASES})


# ---------- robots.txt + sitemap.xml -----------------------------------

PUBLIC_SITEMAP_ROUTES = [
    # (url_name, changefreq, priority)
    ("core:landing",        "monthly", "1.0"),
    ("core:about",          "monthly", "0.8"),
    ("core:contact",        "monthly", "0.6"),
    ("core:security",       "monthly", "0.5"),
    ("core:changelog",      "weekly",  "0.6"),
    ("core:status",         "always",  "0.5"),
    ("core:terms",          "yearly",  "0.3"),
    ("core:privacy",        "yearly",  "0.3"),
    ("core:acceptable_use", "yearly",  "0.4"),
    ("accounts:login",      "yearly",  "0.4"),
    ("accounts:signup",     "yearly",  "0.4"),
    ("accounts:forgot_password", "yearly", "0.2"),
]


def robots_txt(request):
    from django.http import HttpResponse
    from django.urls import reverse
    base = f"{request.scheme}://{request.get_host()}"
    sitemap_url = base + reverse("core:sitemap")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /chat/\n"
        "Disallow: /api/\n"
        "Disallow: /settings/\n"
        "Disallow: /verify/\n"
        "Disallow: /password-reset/\n"
        "Disallow: /2fa/\n"
        "Disallow: /404-preview/\n"
        "Disallow: /500-preview/\n"
        f"\nSitemap: {sitemap_url}\n"
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    from django.http import HttpResponse
    from django.urls import NoReverseMatch, reverse

    base = f"{request.scheme}://{request.get_host()}"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for name, freq, prio in PUBLIC_SITEMAP_ROUTES:
        try:
            path = reverse(name)
        except NoReverseMatch:
            continue
        lines.append("  <url>")
        lines.append(f"    <loc>{base}{path}</loc>")
        lines.append(f"    <changefreq>{freq}</changefreq>")
        lines.append(f"    <priority>{prio}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return HttpResponse("\n".join(lines), content_type="application/xml; charset=utf-8")


def web_manifest(request):
    """Serve the PWA manifest with the correct Content-Type.

    Resolves icon paths through `static()` so they pick up Whitenoise's
    hashed manifest filenames in production. Hardcoded `/static/...` paths
    would 404 because `CompressedManifestStaticFilesStorage` only serves
    hashed variants."""
    import json
    from django.http import HttpResponse
    from django.templatetags.static import static
    payload = {
        "name": "Dark Prompt",
        "short_name": "Dark//Prompt",
        "description": "Local-first LLM frontend for defensive AV / EDR research.",
        "start_url": "/chat/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#000000",
        "theme_color": "#780606",
        "orientation": "any",
        "lang": "en-US",
        "categories": ["productivity", "developer", "security"],
        "icons": [
            {"src": static("img/icon-192.png"),          "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": static("img/icon-512.png"),          "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": static("img/icon-512-maskable.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "New chat", "short_name": "New chat", "url": "/chat/",
             "description": "Start a new generation session"},
            {"name": "Status",   "short_name": "Status",   "url": "/status/",
             "description": "Check the local LLM endpoint"},
        ],
    }
    return HttpResponse(
        json.dumps(payload, indent=2),
        content_type="application/manifest+json",
    )


def legal_terms(request):
    return render(request, "core/legal.html", {
        "doc_title": "Terms of Service",
        "doc_slug": "terms",
        "doc_tag": "// LEGAL · TOS",
    })


def legal_privacy(request):
    return render(request, "core/legal.html", {
        "doc_title": "Privacy Policy",
        "doc_slug": "privacy",
        "doc_tag": "// LEGAL · PRIVACY",
    })


def legal_aup(request):
    return render(request, "core/legal.html", {
        "doc_title": "Acceptable Use Policy",
        "doc_slug": "aup",
        "doc_tag": "// LEGAL · AUP",
    })


def not_found_view(request, exception=None):
    # Wired to handler404 in darkprompt/urls.py. Django invokes this only
    # when DEBUG=False; otherwise it shows the yellow technical 404 page.
    return render(request, "404.html", status=404)


def server_error_view(request):
    # Wired to handler500. DEBUG=False only — debug shows the yellow trace.
    return render(request, "500.html", status=500)


def status_page(request):
    from chat import llm as llm_backend
    return render(request, "core/status.html", {
        "llm_url":   settings.LLM_API_URL,
        "llm_url_c": settings.LLM_API_URL_C,
        "c_available": llm_backend.is_language_available("c"),
    })


def _probe_llm(language="asm"):
    """Best-effort liveness ping for the given backend.
    Returns (state, latency_ms, detail)."""
    from chat import llm as llm_backend

    start = time.monotonic()
    try:
        llm_backend.generate("ping", max_tokens=1, temperature=0.0, language=language)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if elapsed_ms > 2000:
            return ("slow", elapsed_ms, f"latency {elapsed_ms}ms")
        return ("up", elapsed_ms, "OK")
    except llm_backend.LLMTimeout as exc:
        return ("slow", int((time.monotonic() - start) * 1000), exc.detail or "timeout")
    except llm_backend.LLMUnreachable as exc:
        return ("down", int((time.monotonic() - start) * 1000), exc.detail or "unreachable")
    except llm_backend.LLMError as exc:
        # Server reachable but returned an error. Treat as up-but-degraded.
        return ("up", int((time.monotonic() - start) * 1000), (exc.detail or "")[:120])


def api_status(request):
    from chat import llm as llm_backend
    asm_state, asm_lat, asm_detail = _probe_llm("asm")
    payload = {
        "llm": {
            "state": asm_state,
            "latency_ms": asm_lat,
            "detail": asm_detail,
            "endpoint": settings.LLM_API_URL,
        },
        "checked_at": timezone.now().isoformat(),
    }
    if llm_backend.is_language_available("c"):
        c_state, c_lat, c_detail = _probe_llm("c")
        payload["llm_c"] = {
            "state": c_state,
            "latency_ms": c_lat,
            "detail": c_detail,
            "endpoint": settings.LLM_API_URL_C,
        }
    return JsonResponse(payload)
