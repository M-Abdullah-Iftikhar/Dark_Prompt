"""Tiny Groq client for chat-title inference.

Used after the first response of a brand-new conversation: we feed the
user's instruction to a fast Groq model and ask for a 3–6 word title.

Failure modes (no key, network error, weird response, rate limit) all
return None — the caller is expected to fall back to a deterministic
truncation of the prompt so a chat is never untitled.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from django.conf import settings


_TITLE_SYSTEM_PROMPT = (
    "You name a code-generation chat session. "
    "Output a single short, descriptive TITLE for the user's request. "
    "Constraints:\n"
    "- 3 to 6 words.\n"
    "- Title Case.\n"
    "- No quotation marks, no trailing punctuation, no filler words.\n"
    "- No leading 'Title:' or 'Chat:' prefixes.\n"
    "- Plain ASCII letters, numbers and spaces only.\n"
    "Reply with ONLY the title, nothing else."
)


def _clean_title(raw: str) -> Optional[str]:
    if not raw:
        return None
    title = raw.strip()
    # Some models echo "Title: ..." or wrap in quotes despite instructions.
    title = re.sub(r"^\s*(title|chat|name)\s*:\s*", "", title, flags=re.IGNORECASE)
    title = title.strip(" \"'`*•—-").splitlines()[0].strip()
    # Strip residual code-fence backticks or markdown headers.
    title = title.lstrip("# ").strip()
    if not title:
        return None
    # Cap length — Conversation.title is max 255 but a long title looks weird.
    if len(title) > 80:
        title = title[:77].rstrip() + "…"
    return title


def infer_chat_title(prompt: str) -> Optional[str]:
    """Return a Groq-generated title for `prompt`, or None on any failure.

    Synchronous — runs inside the request that just produced the assistant
    response. Worst case adds ~0.5–1.5s to the response time."""
    api_key = (getattr(settings, "GROQ_API_KEY", "") or "").strip()
    if not api_key:
        return None
    try:
        import requests  # transitive dep of gradio_client + huggingface-hub
    except ImportError:
        return None

    try:
        resp = requests.post(
            getattr(settings, "GROQ_API_URL",
                    "https://api.groq.com/openai/v1/chat/completions"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            data=json.dumps({
                "model":       getattr(settings, "GROQ_MODEL", "llama-3.1-8b-instant"),
                "max_tokens":  30,
                "temperature": 0.3,
                "messages": [
                    {"role": "system", "content": _TITLE_SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt[:1000]},
                ],
            }),
            timeout=int(getattr(settings, "GROQ_TIMEOUT", 8)),
        )
        if resp.status_code != 200:
            return None
        body = resp.json()
        content = (
            body.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
        )
        return _clean_title(content)
    except Exception:
        return None
