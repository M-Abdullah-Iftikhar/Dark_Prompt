from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        # Wire signals — auto-create UserProfile on user creation.
        from . import signals  # noqa: F401
