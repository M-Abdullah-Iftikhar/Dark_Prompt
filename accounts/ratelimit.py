"""Tiny IP-based rate limiter built on Django's cache framework.

Avoids pulling in django-ratelimit. Uses fixed-window counters; good enough
for blocking brute-force on auth endpoints in dev + small prod deployments.
"""
import functools
import hashlib

from django.core.cache import cache


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


def _bucket_key(prefix, ip, window_seconds):
    # Hash to keep keys short; window-aligned so each window gets its own counter.
    import time
    window_start = int(time.time() // window_seconds)
    raw = f"{prefix}:{ip}:{window_start}"
    return "rl:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


class RateLimited(Exception):
    """Raised internally; the decorator catches it and renders a 429."""
    def __init__(self, retry_after):
        self.retry_after = retry_after


def check_rate(request, *, prefix, limit, window_seconds):
    """Increment + check the counter. Raises RateLimited if over the cap."""
    ip = _client_ip(request)
    key = _bucket_key(prefix, ip, window_seconds)
    # cache.incr requires the key to exist first.
    if cache.get(key) is None:
        cache.set(key, 0, window_seconds)
    try:
        count = cache.incr(key)
    except ValueError:
        # Race: key expired between get and incr. Re-seed.
        cache.set(key, 1, window_seconds)
        count = 1
    if count > limit:
        raise RateLimited(retry_after=window_seconds)
    return count


def rate_limit(prefix, limit, window_seconds, methods=("POST",)):
    """View decorator: enforce limit per IP within the rolling window.

    Only counts requests whose method is in `methods` (default: POST only),
    so GET renders of the form aren't counted.
    """
    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method in methods:
                try:
                    check_rate(
                        request,
                        prefix=prefix,
                        limit=limit,
                        window_seconds=window_seconds,
                    )
                except RateLimited as exc:
                    from django.shortcuts import render
                    response = render(
                        request,
                        "accounts/rate_limited.html",
                        {"retry_after": exc.retry_after},
                        status=429,
                    )
                    response["Retry-After"] = str(exc.retry_after)
                    return response
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
