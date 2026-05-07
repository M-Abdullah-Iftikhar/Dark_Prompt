"""Helpers for emitting ActivityEvent rows from any view."""
from .models import ActivityEvent


def _client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def _user_agent(request):
    if request is None:
        return ""
    ua = request.META.get("HTTP_USER_AGENT", "")
    return ua[:255]


def log_event(request, kind, *, user=None, detail=""):
    """Best-effort write of an audit row. Never raises into the caller."""
    try:
        target_user = user
        if target_user is None and request is not None:
            target_user = getattr(request, "user", None)
            if target_user is not None and not target_user.is_authenticated:
                target_user = None
        ActivityEvent.objects.create(
            user=target_user,
            kind=kind,
            detail=(detail or "")[:255],
            ip=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except Exception:
        # Audit must never block real work.
        pass
