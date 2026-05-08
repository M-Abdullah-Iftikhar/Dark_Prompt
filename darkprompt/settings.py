"""Django settings for the Dark Prompt project.

Production checklist (also enforced by `python manage.py check --deploy`):
  - DJANGO_DEBUG=0
  - DJANGO_SECRET_KEY set to a random 50+ char value
  - DJANGO_ALLOWED_HOSTS set (comma-separated)
  - DJANGO_CSRF_TRUSTED_ORIGINS set (comma-separated, with scheme)
  - HTTPS-terminating proxy + SECURE_PROXY_SSL_HEADER configured
See `.env.example` for the full env-var contract.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core toggles -----------------------------------------------------------
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

DEV_SECRET_KEY = "dev-only-secret-change-me-in-production-0123456789abcdef"  # noqa: S105
# Treat unset OR empty string as "use the dev fallback" — `.env` files commonly
# carry `DJANGO_SECRET_KEY=` blank entries from .env.example.
SECRET_KEY = (os.environ.get("DJANGO_SECRET_KEY", "") or "").strip() or DEV_SECRET_KEY

ALLOWED_HOSTS = (
    ["*"]
    if DEBUG
    else [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
)
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

# Refuse to boot in prod with a dev secret or wide-open hosts. Skipped for
# build-time management commands (collectstatic / migrate / etc.) so a fresh
# Render service can complete its first build before env vars are filled in.
import sys as _sys
_BUILD_CMDS = {
    "collectstatic", "migrate", "makemigrations", "check", "shell",
    "createsuperuser", "compilemessages", "diffsettings", "loaddata",
    "dumpdata", "test", "showmigrations",
}
_is_build_phase = len(_sys.argv) > 1 and _sys.argv[1] in _BUILD_CMDS

if not DEBUG and not _is_build_phase:
    if SECRET_KEY == DEV_SECRET_KEY:
        raise RuntimeError(
            "DJANGO_SECRET_KEY is unset (using the dev fallback). "
            "Generate a 50+ char random value before running with DEBUG=False."
        )
    if not ALLOWED_HOSTS or ALLOWED_HOSTS == ["*"]:
        raise RuntimeError(
            "DJANGO_ALLOWED_HOSTS must be set to your real host list "
            "(comma-separated) when DEBUG=False."
        )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves static files in production without needing nginx.
    # Must come immediately after SecurityMiddleware.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "darkprompt.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "darkprompt.wsgi.application"

# Database — SQLite locally, whatever DATABASE_URL says in production.
# Render injects DATABASE_URL pointing at its managed Postgres instance.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
_database_url = os.environ.get("DATABASE_URL", "").strip()
if _database_url:
    try:
        import dj_database_url  # noqa: WPS433 — optional in dev, required in prod
        DATABASES["default"] = dj_database_url.parse(
            _database_url,
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    except ImportError:
        # Local dev without the production extras installed — fall through
        # to the SQLite default; printing a warning would spam tests.
        pass

# Logging — write our app's loggers to stderr so Render's log stream picks
# them up. Critical for surfacing SMTP errors that the views otherwise swallow.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "stamped": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "stderr": {
            "class": "logging.StreamHandler",
            "formatter": "stamped",
        },
    },
    "loggers": {
        "accounts": {"handlers": ["stderr"], "level": "INFO", "propagate": False},
        "chat":     {"handlers": ["stderr"], "level": "INFO", "propagate": False},
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Serve compressed + hashed static files in production via WhiteNoise.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth flow
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "chat:chat"
LOGOUT_REDIRECT_URL = "core:landing"

# Allow login by email or username — handled in accounts.backends
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Local LLM backends — exposed as Gradio spaces (Kaggle / HF Spaces / etc.).
# The URLs must be the *base* of the gradio app, not the /generate endpoint.
#
# Two models are wired up: an Assembly (asm) generator and a C generator.
# Each conversation is stamped at creation with the language it was started
# in; the chat backend routes its prompts to the matching model and refuses
# to switch within an existing conversation.
LLM_API_URL      = os.environ.get("LLM_API_URL",      "http://127.0.0.1:7860")  # asm
LLM_API_NAME     = os.environ.get("LLM_API_NAME",     "/generate")
LLM_API_URL_C    = os.environ.get("LLM_API_URL_C",    "")                       # c (optional)
LLM_API_NAME_C   = os.environ.get("LLM_API_NAME_C",   "/generate")
LLM_API_TIMEOUT  = int(os.environ.get("LLM_API_TIMEOUT", "120"))  # reserved for future use

# Email — dev prints to console; prod swaps to SMTP via env vars.
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST          = os.environ.get("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT          = int(os.environ.get("DJANGO_EMAIL_PORT", "25"))
EMAIL_HOST_USER     = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS       = os.environ.get("DJANGO_EMAIL_USE_TLS", "0") == "1"
DEFAULT_FROM_EMAIL  = os.environ.get(
    "DJANGO_DEFAULT_FROM_EMAIL",
    "Dark Prompt <no-reply@darkprompt.local>",
)
PASSWORD_RESET_TIMEOUT = 60 * 30  # 30 minutes

# HTTPS email API keys (used when the platform blocks SMTP egress, e.g.
# Render's free tier). Pick one provider, set its key, and point
# DJANGO_EMAIL_BACKEND at the matching backend class.
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
BREVO_API_KEY  = os.environ.get("BREVO_API_KEY",  "")

# Stripe — used in TEST MODE for now (sk_test_… / pk_test_… keys). Flip the
# keys to live values when ready for production. The Price IDs come from the
# Stripe dashboard after you create products for each tier.
STRIPE_SECRET_KEY      = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET  = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_EXPLOIT   = os.environ.get("STRIPE_PRICE_EXPLOIT", "")
STRIPE_PRICE_ZERODAY   = os.environ.get("STRIPE_PRICE_ZERODAY", "")

# Cost telemetry — synthetic dollar rate per 1k tokens for the local LLM.
# Configurable via env so it can be tuned without a redeploy.
LLM_COST_PER_1K_TOKENS = float(os.environ.get("LLM_COST_PER_1K_TOKENS", "0.0005"))

# Groq — used for chat-title inference (and other small AI-agent helpers).
# Empty key disables the feature (titles fall back to a truncation of the
# first user prompt).
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = os.environ.get("GROQ_MODEL",   "llama-3.1-8b-instant")
GROQ_API_URL = os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_TIMEOUT = int(os.environ.get("GROQ_TIMEOUT", "8"))

# CORS — applies only to /api/chat/ (the public, API-key-callable endpoint).
# Comma-separated list of exact origins ("https://example.com").
# Use "*" to allow any origin (only meaningful for non-credentialed requests).
# Empty / unset → same-origin only (preflight requests are rejected).
LLM_CORS_ALLOW_ORIGINS = [
    o.strip()
    for o in os.environ.get("LLM_CORS_ALLOW_ORIGINS", "").split(",")
    if o.strip()
]

# --- Cookie + transport security -------------------------------------------
# Defaults flip with DEBUG; override per-flag if your terminating proxy
# already handles HTTPS but talks plain to Django.
SESSION_COOKIE_SECURE  = os.environ.get("DJANGO_SESSION_COOKIE_SECURE", "0" if DEBUG else "1") == "1"
CSRF_COOKIE_SECURE     = os.environ.get("DJANGO_CSRF_COOKIE_SECURE",    "0" if DEBUG else "1") == "1"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE    = "Lax"

SECURE_BROWSER_XSS_FILTER     = True
SECURE_CONTENT_TYPE_NOSNIFF   = True
SECURE_REFERRER_POLICY        = "same-origin"
X_FRAME_OPTIONS               = "DENY"

if not DEBUG:
    # When traffic terminates HTTPS at a reverse proxy that forwards as HTTP,
    # set DJANGO_BEHIND_TLS_PROXY=1 so request.is_secure() is honest.
    if os.environ.get("DJANGO_BEHIND_TLS_PROXY", "0") == "1":
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT  = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
    SECURE_HSTS_SECONDS  = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
    SECURE_HSTS_PRELOAD            = SECURE_HSTS_SECONDS > 0
