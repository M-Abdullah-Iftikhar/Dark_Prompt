"""Account-side models: ActivityEvent (audit feed), ApiKey (operator tokens)."""
import hashlib
import secrets

from django.conf import settings
from django.db import models


class ActivityEvent(models.Model):
    LOGIN                = "login"
    LOGIN_FAILED         = "login_failed"
    LOGOUT               = "logout"
    SIGNUP               = "signup"
    PASSWORD_CHANGE      = "password_change"
    PASSWORD_RESET       = "password_reset"
    PROFILE_UPDATE       = "profile_update"
    CONVERSATION_DELETE  = "conversation_delete"
    CONVERSATION_RENAME  = "conversation_rename"
    CONVERSATION_EXPORT  = "conversation_export"
    SUBSCRIPTION_ACTIVATE = "subscription_activate"

    KIND_CHOICES = [
        (LOGIN,                "Login"),
        (LOGIN_FAILED,         "Login failed"),
        (LOGOUT,               "Logout"),
        (SIGNUP,               "Signup"),
        (PASSWORD_CHANGE,      "Password change"),
        (PASSWORD_RESET,       "Password reset"),
        (PROFILE_UPDATE,       "Profile update"),
        (CONVERSATION_DELETE,  "Conversation deleted"),
        (CONVERSATION_RENAME,  "Conversation renamed"),
        (CONVERSATION_EXPORT,  "Conversation exported"),
        (SUBSCRIPTION_ACTIVATE, "Subscription activated"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_events",
        null=True, blank=True,
    )
    kind       = models.CharField(max_length=40, choices=KIND_CHOICES)
    detail     = models.CharField(max_length=255, blank=True, default="")
    ip         = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        u = self.user.username if self.user_id else "anon"
        return f"{u} · {self.kind} @ {self.created_at:%Y-%m-%d %H:%M}"


class UserProfile(models.Model):
    """One row per user — extra account-side state without forking AUTH_USER_MODEL."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    email_verified_at  = models.DateTimeField(null=True, blank=True)
    last_verify_sent   = models.DateTimeField(null=True, blank=True)
    totp_secret        = models.CharField(max_length=64, blank=True, default="")
    totp_confirmed_at  = models.DateTimeField(null=True, blank=True)
    backup_codes_hash  = models.TextField(blank=True, default="")  # newline-separated SHA256 hashes

    @property
    def email_verified(self):
        return self.email_verified_at is not None

    @property
    def totp_enabled(self):
        return self.totp_confirmed_at is not None

    def __str__(self):
        return f"profile<{self.user.username}>"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ApiKey(models.Model):
    """Personal token a user can use to hit /api/chat/ from their own scripts.

    Tokens are stored hashed; the raw value is shown to the user exactly once
    at creation. Each key has a short prefix used for display / lookup.
    """
    PREFIX = "dpk_"
    TOKEN_BYTES = 32

    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name        = models.CharField(max_length=80)
    prefix      = models.CharField(max_length=12, db_index=True)
    key_hash    = models.CharField(max_length=64, unique=True)
    last_used   = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    revoked_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def generate(cls, *, user, name):
        """Create a new key, return (instance, raw_token).

        The raw_token is only available right now — afterwards we only have
        its hash on disk."""
        raw = cls.PREFIX + secrets.token_urlsafe(cls.TOKEN_BYTES)
        instance = cls.objects.create(
            user=user,
            name=(name or "API key")[:80],
            prefix=raw[: len(cls.PREFIX) + 6],
            key_hash=_hash_token(raw),
        )
        return instance, raw

    @classmethod
    def lookup(cls, raw_token):
        """Return the active key matching this token, or None."""
        if not raw_token or not raw_token.startswith(cls.PREFIX):
            return None
        try:
            return cls.objects.select_related("user").get(
                key_hash=_hash_token(raw_token),
                revoked_at__isnull=True,
            )
        except cls.DoesNotExist:
            return None

    @property
    def is_active(self):
        return self.revoked_at is None

    def __str__(self):
        return f"{self.user.username} · {self.name} ({self.prefix}…)"
