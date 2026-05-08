"""HTTPS-based email backends that work on platforms blocking SMTP egress
(Render free tier, most cloud providers' free instances, Vercel, etc.).

Three backends are provided, all interchangeable. Pick whichever your
provider gives you a key for:

ResendBackend — https://resend.com  (3000 emails/mo free, needs domain
verification before you can send to anyone other than your signup email).

BrevoBackend — https://brevo.com  (300 emails/day free, single-sender
verification: confirm one FROM email and you can send to ANY recipient).
Best fit when you don't own a domain.

Usage — set in env::

    DJANGO_EMAIL_BACKEND=accounts.email_backends.BrevoBackend
    BREVO_API_KEY=xkeysib-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    DJANGO_DEFAULT_FROM_EMAIL=Dark Prompt <verified@example.com>
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


# ---------------------------------------------------------------------------
# Brevo (formerly Sendinblue)
# ---------------------------------------------------------------------------

def _split_email(addr: str) -> dict:
    """Parse 'Name <email@x>' or 'email@x' into Brevo's {name, email} shape."""
    if not addr:
        return {"email": ""}
    addr = addr.strip()
    if "<" in addr and ">" in addr:
        name, _, rest = addr.partition("<")
        email = rest.rstrip(">").strip()
        return {"name": name.strip().strip('"'), "email": email}
    return {"email": addr}


class BrevoBackend(BaseEmailBackend):
    """Send `EmailMessage` objects via Brevo's HTTPS transactional API.

    Brevo's free tier requires only a single-sender verification (one click
    on a confirmation email) — no DNS records, no domain ownership. Perfect
    for an FYP demo where you don't want to buy a domain. Quota: 300/day."""

    api_url = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = (getattr(settings, "BREVO_API_KEY", "") or "").strip()

    def send_messages(self, email_messages: Iterable) -> int:
        if not email_messages:
            return 0
        if not self.api_key:
            msg = "BREVO_API_KEY is not configured."
            if self.fail_silently:
                log.error(msg)
                return 0
            raise RuntimeError(msg)

        try:
            import requests
        except ImportError as exc:
            if self.fail_silently:
                return 0
            raise RuntimeError("`requests` is required for BrevoBackend") from exc

        sent = 0
        for message in email_messages:
            from_addr = message.from_email or settings.DEFAULT_FROM_EMAIL
            payload = {
                "sender":      _split_email(from_addr),
                "to":          [_split_email(addr) for addr in (message.to or [])],
                "subject":     message.subject or "",
                "textContent": message.body or "",
            }
            if getattr(message, "cc", None):
                payload["cc"] = [_split_email(a) for a in message.cc]
            if getattr(message, "bcc", None):
                payload["bcc"] = [_split_email(a) for a in message.bcc]
            if getattr(message, "reply_to", None) and message.reply_to:
                payload["replyTo"] = _split_email(message.reply_to[0])

            for body, content_type in getattr(message, "alternatives", []) or []:
                if content_type == "text/html":
                    payload["htmlContent"] = body
                    break

            try:
                resp = requests.post(
                    self.api_url,
                    headers={
                        "api-key":      self.api_key,
                        "Accept":       "application/json",
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(payload),
                    timeout=10,
                )
            except Exception:
                log.exception("Brevo HTTP error")
                if not self.fail_silently:
                    raise
                continue

            if 200 <= resp.status_code < 300:
                sent += 1
            else:
                detail = resp.text[:400] if resp.text else f"HTTP {resp.status_code}"
                log.error("Brevo rejected message: %s", detail)
                if not self.fail_silently:
                    raise RuntimeError(f"Brevo rejected message: {detail}")

        return sent
