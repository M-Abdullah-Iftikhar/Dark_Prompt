"""HTTPS-based email backends that work on platforms blocking SMTP egress
(Render free tier, most cloud providers' free instances, Vercel, etc.).

Usage — set in env::

    DJANGO_EMAIL_BACKEND=accounts.email_backends.ResendBackend
    RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
    DJANGO_DEFAULT_FROM_EMAIL=Dark Prompt <onboarding@resend.dev>

Resend's onboarding sender domain (onboarding@resend.dev) works without DNS
verification and is fine for an FYP demo. Production / real users want a
verified custom domain — see https://resend.com/domains.
"""
from __future__ import annotations

import json
import logging
from typing import Iterable

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

log = logging.getLogger("accounts.email")


class ResendBackend(BaseEmailBackend):
    """Send `EmailMessage` objects via Resend's HTTPS API.

    Compatible with anywhere Django's standard `send_mail` is used —
    so password-reset, verification, etc. all work without code changes."""

    api_url = "https://api.resend.com/emails"

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = (getattr(settings, "RESEND_API_KEY", "") or "").strip()

    def send_messages(self, email_messages: Iterable) -> int:
        if not email_messages:
            return 0
        if not self.api_key:
            msg = "RESEND_API_KEY is not configured."
            if self.fail_silently:
                log.error(msg)
                return 0
            raise RuntimeError(msg)

        try:
            import requests
        except ImportError as exc:
            if self.fail_silently:
                return 0
            raise RuntimeError("`requests` is required for ResendBackend") from exc

        sent = 0
        for message in email_messages:
            payload = {
                "from":    message.from_email or settings.DEFAULT_FROM_EMAIL,
                "to":      list(message.to or []),
                "subject": message.subject or "",
                "text":    message.body or "",
            }
            if getattr(message, "cc", None):
                payload["cc"] = list(message.cc)
            if getattr(message, "bcc", None):
                payload["bcc"] = list(message.bcc)
            if getattr(message, "reply_to", None):
                payload["reply_to"] = list(message.reply_to)

            # If the message carries an HTML alternative, send that too.
            for body, content_type in getattr(message, "alternatives", []) or []:
                if content_type == "text/html":
                    payload["html"] = body
                    break

            try:
                resp = requests.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type":  "application/json",
                    },
                    data=json.dumps(payload),
                    timeout=10,
                )
            except Exception as exc:
                log.exception("Resend HTTP error")
                if not self.fail_silently:
                    raise
                continue

            if resp.status_code >= 200 and resp.status_code < 300:
                sent += 1
            else:
                detail = resp.text[:400] if resp.text else f"HTTP {resp.status_code}"
                log.error("Resend rejected message: %s", detail)
                if not self.fail_silently:
                    raise RuntimeError(f"Resend rejected message: {detail}")

        return sent
