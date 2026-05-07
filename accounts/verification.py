"""Email verification — stateless signed tokens, no extra DB rows.

The token carries the user_id + email so that if the user changes their email
before clicking the link, the link is automatically invalidated.
"""
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

VERIFY_SALT = "dp.email-verify.v1"
VERIFY_MAX_AGE = 60 * 60 * 24  # 24 hours
RESEND_COOLDOWN = 60            # 60 seconds between resends


def make_token(user):
    return signing.dumps(
        {"uid": user.pk, "email": user.email},
        salt=VERIFY_SALT,
    )


def parse_token(token):
    """Return {uid, email} dict on success, None on failure / expiry."""
    try:
        return signing.loads(token, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)
    except signing.BadSignature:
        return None


def send_verification_email(request, user):
    """Send a verification email and stamp the cooldown on the profile.

    Returns True if the email was actually sent, False if the cooldown
    short-circuited.
    """
    profile = getattr(user, "profile", None)
    if profile is not None:
        if profile.last_verify_sent is not None:
            elapsed = (timezone.now() - profile.last_verify_sent).total_seconds()
            if elapsed < RESEND_COOLDOWN:
                return False

    token = make_token(user)
    path = reverse("accounts:verify_email", args=[token])
    verify_url = request.build_absolute_uri(path)

    subject = "Dark Prompt — verify your access"
    body = render_to_string("accounts/email/verify_email.txt", {
        "user": user,
        "verify_url": verify_url,
        "expires_hours": int(VERIFY_MAX_AGE // 3600),
    })
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    if profile is not None:
        profile.last_verify_sent = timezone.now()
        profile.save(update_fields=["last_verify_sent"])
    return True
