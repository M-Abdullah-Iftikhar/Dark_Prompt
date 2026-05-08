"""Authentication views."""
import logging

from django.conf import settings
from django.contrib import messages

log = logging.getLogger("accounts.email")
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods

from .activity import log_event
from .forms import (
    ForgotPasswordForm,
    LoginForm,
    PasswordChangeForm,
    PasswordResetConfirmForm,
    SettingsForm,
    SignupForm,
    SubscriptionAgreementForm,
    TOTPChallengeForm,
    TOTPDisableForm,
    TOTPSetupForm,
)
from .models import ActivityEvent, ApiKey, UserProfile
from .ratelimit import rate_limit
from . import totp as totplib
from .verification import parse_token, send_verification_email

User = get_user_model()

SESSION_REMEMBER_AGE = 60 * 60 * 24 * 30  # 30 days


def _finalize_login(request, user, *, remember_me=False):
    """Finish the login: bind session, stamp metadata, and audit."""
    from django.utils import timezone as _tz
    login(request, user)
    if remember_me:
        request.session.set_expiry(SESSION_REMEMBER_AGE)
    else:
        request.session.set_expiry(0)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.META.get("REMOTE_ADDR") or "")
    request.session["_dp_user_agent"] = (request.META.get("HTTP_USER_AGENT") or "")[:255]
    request.session["_dp_ip"] = ip[:45]
    request.session["_dp_created_at"] = _tz.now().isoformat()
    log_event(request, ActivityEvent.LOGIN, user=user)

TIER_INFO = {
    "sniffer":  {"name": "SNIFFER",   "tag": "TIER 01", "tagline": "Just listening in",  "price": "$0",   "cta": "Activate Sniffer"},
    "exploit":  {"name": "EXPLOIT",   "tag": "TIER 02", "tagline": "Finding the gaps",   "price": "$29",  "cta": "Activate Exploit"},
    "zeroday":  {"name": "ZERO DAY",  "tag": "TIER 03", "tagline": "Unstoppable",        "price": "$149", "cta": "Activate Zero Day"},
}


@rate_limit(prefix="signup", limit=5, window_seconds=3600)  # 5 per IP per hour
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("chat:chat")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            authed = authenticate(
                request,
                username=user.username,
                password=form.cleaned_data["password"],
            )
            if authed is not None:
                login(request, authed)
                log_event(request, ActivityEvent.SIGNUP, user=authed)
                try:
                    send_verification_email(request, authed)
                except Exception:
                    log.exception("send_verification_email failed during signup for user_id=%s", authed.pk)
            return redirect("accounts:verify_pending")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})


@rate_limit(prefix="login", limit=10, window_seconds=300)  # 10 per IP per 5 min
def login_view(request):
    if request.user.is_authenticated:
        return redirect("chat:chat")
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["identifier"],
                password=form.cleaned_data["password"],
            )
            if user is None:
                form.add_error(None, "Invalid credentials.")
                log_event(
                    request, ActivityEvent.LOGIN_FAILED,
                    detail=form.cleaned_data.get("identifier", "")[:120],
                )
            else:
                profile = getattr(user, "profile", None)
                if profile is not None and profile.totp_enabled:
                    # Defer login() — first prove possession of the TOTP device.
                    request.session["pending_2fa_uid"]      = user.pk
                    request.session["pending_2fa_remember"] = bool(form.cleaned_data.get("remember_me"))
                    request.session["pending_2fa_next"]     = request.GET.get("next") or ""
                    return redirect("accounts:totp_challenge")
                _finalize_login(request, user, remember_me=form.cleaned_data.get("remember_me"))
                next_url = request.GET.get("next") or reverse("chat:chat")
                return redirect(next_url)
    else:
        form = LoginForm()
    return render(request, "accounts/login.html", {"form": form})


@require_http_methods(["POST"])
def logout_view(request):
    if request.user.is_authenticated:
        log_event(request, ActivityEvent.LOGOUT)
    logout(request)
    return redirect("core:landing")


@login_required(login_url="accounts:login")
def settings_view(request):
    profile_form = SettingsForm(user=request.user, initial={
        "username": request.user.username,
        "email": request.user.email,
    })
    password_form = PasswordChangeForm(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "profile":
            profile_form = SettingsForm(request.POST, user=request.user)
            if profile_form.is_valid():
                request.user.username = profile_form.cleaned_data["username"]
                request.user.email = profile_form.cleaned_data["email"]
                request.user.save(update_fields=["username", "email"])
                log_event(request, ActivityEvent.PROFILE_UPDATE)
                messages.success(request, "Profile updated.")
                return redirect("accounts:settings")
        elif action == "password":
            password_form = PasswordChangeForm(request.POST, user=request.user)
            if password_form.is_valid():
                request.user.set_password(password_form.cleaned_data["new_password"])
                request.user.save()
                # Keep the session alive after password change
                update_session_auth_hash(request, request.user)
                log_event(request, ActivityEvent.PASSWORD_CHANGE)
                messages.success(request, "Password changed.")
                return redirect("accounts:settings")

    return render(request, "accounts/settings.html", {
        "profile_form": profile_form,
        "password_form": password_form,
        "active_tier": request.session.get("tier"),
    })


def _send_password_reset_email(request, user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token  = default_token_generator.make_token(user)
    path   = reverse("accounts:password_reset_confirm", args=[uidb64, token])
    reset_url = request.build_absolute_uri(path)
    ctx = {
        "user": user,
        "reset_url": reset_url,
        "expires_minutes": int(settings.PASSWORD_RESET_TIMEOUT // 60),
    }
    subject = "Dark Prompt — reset your access key"
    body = render_to_string("accounts/email/password_reset.txt", ctx)
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


@rate_limit(prefix="forgot", limit=5, window_seconds=3600)  # 5 per IP per hour
def forgot_password_view(request):
    sent = False
    if request.method == "POST":
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            # Always show success regardless of match, to avoid leaking
            # which addresses are registered. Only actually send when matched.
            for user in User.objects.filter(email__iexact=email, is_active=True):
                try:
                    _send_password_reset_email(request, user)
                except Exception:
                    log.exception("password reset email failed for user_id=%s", user.pk)
            sent = True
    else:
        form = ForgotPasswordForm()
    return render(request, "accounts/forgot_password.html", {"form": form, "sent": sent})


def password_reset_confirm_view(request, uidb64, token):
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    valid = user is not None and default_token_generator.check_token(user, token)

    if not valid:
        return render(request, "accounts/password_reset_confirm.html", {
            "valid": False,
        })

    done = False
    if request.method == "POST":
        form = PasswordResetConfirmForm(request.POST, user=user)
        if form.is_valid():
            user.set_password(form.cleaned_data["new_password"])
            user.save()
            log_event(request, ActivityEvent.PASSWORD_RESET, user=user)
            done = True
            form = None
    else:
        form = PasswordResetConfirmForm(user=user)

    return render(request, "accounts/password_reset_confirm.html", {
        "valid": True,
        "done": done,
        "form": form,
    })


@login_required(login_url="accounts:login")
def subscribe_view(request, tier):
    info = TIER_INFO.get(tier)
    if info is None:
        raise Http404("Unknown tier.")
    if request.method == "POST":
        form = SubscriptionAgreementForm(request.POST)
        if form.is_valid():
            # Stub activation — record on session. Wire to billing + DB later.
            request.session["tier"] = tier
            request.session["tier_signed_at"] = form.cleaned_data["signature"]
            log_event(
                request, ActivityEvent.SUBSCRIPTION_ACTIVATE,
                detail=info["name"],
            )
            messages.success(request, f"{info['name']} activated. Welcome aboard.")
            return redirect("chat:chat")
    else:
        form = SubscriptionAgreementForm()
    return render(request, "accounts/subscribe.html", {
        "form": form,
        "tier": tier,
        "info": info,
    })


@login_required(login_url="accounts:login")
def verify_pending_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.email_verified:
        return redirect("chat:chat")
    return render(request, "accounts/verify_pending.html", {"profile": profile})


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
@rate_limit(prefix="verify_resend", limit=5, window_seconds=3600)
def verify_resend_view(request):
    if getattr(request.user.profile, "email_verified", False):
        messages.info(request, "Email is already verified.")
        return redirect("chat:chat")
    sent = False
    try:
        sent = send_verification_email(request, request.user)
    except Exception:
        log.exception("verify resend failed for user_id=%s", request.user.pk)
        sent = False
    if sent:
        messages.success(request, "Verification email re-sent. Check your inbox.")
    else:
        messages.error(request, "Please wait a minute before requesting another link.")
    return redirect("accounts:verify_pending")


def verify_email_view(request, token):
    payload = parse_token(token)
    valid = False
    if payload is not None:
        try:
            user = User.objects.get(pk=payload.get("uid"))
        except User.DoesNotExist:
            user = None
        if user is not None and (payload.get("email") or "").lower() == (user.email or "").lower():
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if not profile.email_verified:
                from django.utils import timezone as _tz
                profile.email_verified_at = _tz.now()
                profile.save(update_fields=["email_verified_at"])
                log_event(request, ActivityEvent.PROFILE_UPDATE, user=user, detail="email verified")
            valid = True
    return render(request, "accounts/verify_email.html", {"valid": valid})


@rate_limit(prefix="totp", limit=10, window_seconds=300)
def totp_challenge_view(request):
    """Login-time 2FA challenge. Reads user_id from the pending session bag."""
    uid = request.session.get("pending_2fa_uid")
    if not uid:
        return redirect("accounts:login")
    try:
        user = User.objects.get(pk=uid)
    except User.DoesNotExist:
        request.session.pop("pending_2fa_uid", None)
        return redirect("accounts:login")
    profile = getattr(user, "profile", None)
    if profile is None or not profile.totp_enabled:
        # Lost state — start over.
        request.session.pop("pending_2fa_uid", None)
        return redirect("accounts:login")

    form = TOTPChallengeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["code"]
        if totplib.verify(profile.totp_secret, code):
            ok = True
            via = "totp"
        elif totplib.consume_backup_code(profile, code):
            ok = True
            via = "backup_code"
        else:
            ok = False
            via = None
        if ok:
            remember = bool(request.session.get("pending_2fa_remember", False))
            next_url = request.session.get("pending_2fa_next") or ""
            for k in ("pending_2fa_uid", "pending_2fa_remember", "pending_2fa_next"):
                request.session.pop(k, None)
            _finalize_login(request, user, remember_me=remember)
            log_event(request, ActivityEvent.LOGIN, user=user, detail=f"2fa: {via}")
            return redirect(next_url or reverse("chat:chat"))
        form.add_error("code", "Invalid 2FA code.")
        log_event(request, ActivityEvent.LOGIN_FAILED, user=user, detail="2fa rejected")

    return render(request, "accounts/totp_challenge.html", {
        "form": form,
        "remaining_codes": totplib.remaining_backup_codes(profile),
    })


@login_required(login_url="accounts:login")
def totp_setup_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.totp_enabled:
        return redirect("accounts:totp_manage")

    secret = request.session.get("pending_totp_secret")
    if not secret:
        secret = totplib.generate_secret()
        request.session["pending_totp_secret"] = secret

    form = TOTPSetupForm(request.POST or None)
    confirmed = False
    backup_codes = None

    if request.method == "POST" and form.is_valid():
        if totplib.verify(secret, form.cleaned_data["code"]):
            from django.utils import timezone as _tz
            raw_codes = totplib.generate_backup_codes()
            profile.totp_secret = secret
            profile.totp_confirmed_at = _tz.now()
            profile.backup_codes_hash = totplib.hash_codes(raw_codes)
            profile.save(update_fields=[
                "totp_secret", "totp_confirmed_at", "backup_codes_hash",
            ])
            request.session.pop("pending_totp_secret", None)
            log_event(request, ActivityEvent.PROFILE_UPDATE, detail="2fa enabled")
            confirmed = True
            backup_codes = raw_codes
        else:
            form.add_error("code", "Code did not match. Re-sync your authenticator clock and try again.")

    uri = totplib.provisioning_uri(secret, account_name=request.user.email or request.user.username)
    return render(request, "accounts/totp_setup.html", {
        "form": form,
        "secret": secret,
        "uri": uri,
        "confirmed": confirmed,
        "backup_codes": backup_codes,
    })


@login_required(login_url="accounts:login")
def totp_manage_view(request):
    """Management page for users who already have TOTP enabled."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.totp_enabled:
        return redirect("accounts:totp_setup")

    disable_form = TOTPDisableForm(user=request.user)
    new_codes = None

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "disable":
            disable_form = TOTPDisableForm(request.POST, user=request.user)
            if disable_form.is_valid():
                profile.totp_secret = ""
                profile.totp_confirmed_at = None
                profile.backup_codes_hash = ""
                profile.save(update_fields=[
                    "totp_secret", "totp_confirmed_at", "backup_codes_hash",
                ])
                log_event(request, ActivityEvent.PROFILE_UPDATE, detail="2fa disabled")
                messages.success(request, "Two-factor authentication disabled.")
                return redirect("accounts:settings")
        elif action == "regenerate_codes":
            raw = totplib.generate_backup_codes()
            profile.backup_codes_hash = totplib.hash_codes(raw)
            profile.save(update_fields=["backup_codes_hash"])
            log_event(request, ActivityEvent.PROFILE_UPDATE, detail="2fa backup codes regenerated")
            new_codes = raw
            messages.success(request, "New backup codes generated. Save them somewhere safe.")

    return render(request, "accounts/totp_manage.html", {
        "profile": profile,
        "disable_form": disable_form,
        "new_codes": new_codes,
        "remaining_codes": totplib.remaining_backup_codes(profile),
    })


@login_required(login_url="accounts:login")
def activity_view(request):
    events = list(
        ActivityEvent.objects.filter(user=request.user).order_by("-created_at", "-id")[:50]
    )
    return render(request, "accounts/activity.html", {"events": events})


def _parse_user_agent(ua):
    """Best-effort label for a User-Agent string. Pure stdlib, no deps."""
    if not ua:
        return ("Unknown device", "")
    s = ua.lower()
    if "iphone" in s or "ipad" in s:           os_label = "iOS"
    elif "android" in s:                       os_label = "Android"
    elif "windows" in s:                       os_label = "Windows"
    elif "mac os x" in s or "macintosh" in s:  os_label = "macOS"
    elif "linux" in s:                         os_label = "Linux"
    else:                                      os_label = "Unknown OS"
    if "edg/" in s:           browser = "Edge"
    elif "firefox/" in s:     browser = "Firefox"
    elif "chrome/" in s and "chromium" not in s: browser = "Chrome"
    elif "safari/" in s:      browser = "Safari"
    elif "curl/" in s:        browser = "curl"
    elif "python" in s:       browser = "Python client"
    else:                     browser = "Unknown browser"
    return (f"{browser} on {os_label}", ua)


@login_required(login_url="accounts:login")
def sessions_view(request):
    from django.contrib.sessions.models import Session
    from django.utils import timezone as tz

    current_key = request.session.session_key
    rows = []
    for session in Session.objects.filter(expire_date__gt=tz.now()):
        try:
            data = session.get_decoded()
        except Exception:
            continue
        uid = data.get("_auth_user_id")
        if str(uid) != str(request.user.pk):
            continue
        label, ua_full = _parse_user_agent(data.get("_dp_user_agent", ""))
        rows.append({
            "key": session.session_key,
            "label": label,
            "ua_full": ua_full,
            "ip": data.get("_dp_ip", ""),
            "created_at": data.get("_dp_created_at"),
            "expire_date": session.expire_date,
            "is_current": session.session_key == current_key,
        })
    rows.sort(key=lambda r: (not r["is_current"], r["expire_date"]), reverse=True)
    return render(request, "accounts/sessions.html", {"sessions": rows})


@login_required(login_url="accounts:login")
def api_keys_view(request):
    """List + create API keys. Newly minted raw token is flashed once."""
    new_token = None
    if request.method == "POST":
        action = request.POST.get("action", "create")
        if action == "create":
            name = (request.POST.get("name") or "").strip() or "API key"
            instance, raw = ApiKey.generate(user=request.user, name=name)
            log_event(
                request, ActivityEvent.PROFILE_UPDATE,
                detail=f"created API key: {instance.name} ({instance.prefix}…)",
            )
            new_token = raw
            messages.success(
                request,
                "Key created. Copy it now — you won't see the raw value again.",
            )
        elif action == "revoke":
            key_id = request.POST.get("key_id")
            try:
                obj = ApiKey.objects.get(pk=key_id, user=request.user, revoked_at__isnull=True)
            except (ApiKey.DoesNotExist, ValueError):
                obj = None
            if obj is not None:
                from django.utils import timezone as _tz
                obj.revoked_at = _tz.now()
                obj.save(update_fields=["revoked_at"])
                log_event(
                    request, ActivityEvent.PROFILE_UPDATE,
                    detail=f"revoked API key: {obj.name} ({obj.prefix}…)",
                )
                messages.success(request, "Key revoked.")
            else:
                messages.error(request, "Key not found or already revoked.")
            return redirect("accounts:api_keys")

    keys = list(ApiKey.objects.filter(user=request.user).order_by("-created_at"))
    return render(request, "accounts/api_keys.html", {
        "keys": keys,
        "new_token": new_token,
    })


@login_required(login_url="accounts:login")
@require_http_methods(["POST"])
def session_revoke_view(request, key):
    from django.contrib.sessions.models import Session
    if key == request.session.session_key:
        messages.error(request, "Use Sign out to end your current session.")
        return redirect("accounts:sessions")
    try:
        session = Session.objects.get(session_key=key)
    except Session.DoesNotExist:
        messages.error(request, "That session is no longer active.")
        return redirect("accounts:sessions")
    try:
        data = session.get_decoded()
        if str(data.get("_auth_user_id")) != str(request.user.pk):
            messages.error(request, "That session does not belong to you.")
            return redirect("accounts:sessions")
    except Exception:
        messages.error(request, "Could not decode that session.")
        return redirect("accounts:sessions")
    session.delete()
    messages.success(request, "Session revoked.")
    return redirect("accounts:sessions")
