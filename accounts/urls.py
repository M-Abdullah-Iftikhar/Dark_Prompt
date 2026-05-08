from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("settings/", views.settings_view, name="settings"),
    path("settings/activity/", views.activity_view, name="activity"),
    path("settings/sessions/", views.sessions_view, name="sessions"),
    path("settings/sessions/<str:key>/revoke/", views.session_revoke_view, name="session_revoke"),
    path("settings/api-keys/", views.api_keys_view, name="api_keys"),
    path("settings/2fa/setup/",  views.totp_setup_view,  name="totp_setup"),
    path("settings/2fa/manage/", views.totp_manage_view, name="totp_manage"),
    path("2fa/", views.totp_challenge_view, name="totp_challenge"),
    path("verify/", views.verify_pending_view, name="verify_pending"),
    path("verify/resend/", views.verify_resend_view, name="verify_resend"),
    path("verify/<str:token>/", views.verify_email_view, name="verify_email"),
    path("forgot-password/", views.forgot_password_view, name="forgot_password"),
    path(
        "password-reset/<slug:uidb64>/<slug:token>/",
        views.password_reset_confirm_view,
        name="password_reset_confirm",
    ),
    # Stripe / billing — these MUST come BEFORE the generic subscribe/<slug:tier>/
    # route, otherwise Django matches "subscribe/success/" against the slug
    # pattern (with tier="success") and 404s in subscribe_view.
    path("subscribe/success/", views.subscribe_success_view, name="subscribe_success"),
    path("subscribe/cancel/",  views.subscribe_cancel_view,  name="subscribe_cancel"),
    path("billing/portal/",    views.billing_portal_view,    name="billing_portal"),
    path("billing/webhook/",   views.stripe_webhook_view,    name="stripe_webhook"),
    path("subscribe/<slug:tier>/", views.subscribe_view, name="subscribe"),
]
