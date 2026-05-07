"""Add UserProfile (verification + TOTP state) and backfill rows."""
from django.conf import settings
from django.db import migrations, models


def backfill_profiles(apps, schema_editor):
    """Create a profile for every pre-existing user, and grandfather them in
    as already-verified — they predate the verification feature."""
    from django.utils import timezone
    UserProfile = apps.get_model("accounts", "UserProfile")
    User = apps.get_model(settings.AUTH_USER_MODEL.split(".")[0], settings.AUTH_USER_MODEL.split(".")[1])
    now = timezone.now()
    for user in User.objects.all():
        profile, created = UserProfile.objects.get_or_create(user=user)
        if profile.email_verified_at is None:
            profile.email_verified_at = now
            profile.save(update_fields=["email_verified_at"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_apikey"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email_verified_at", models.DateTimeField(blank=True, null=True)),
                ("last_verify_sent", models.DateTimeField(blank=True, null=True)),
                ("totp_secret", models.CharField(blank=True, default="", max_length=64)),
                ("totp_confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("backup_codes_hash", models.TextField(blank=True, default="")),
                ("user", models.OneToOneField(
                    on_delete=models.deletion.CASCADE,
                    related_name="profile",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.RunPython(backfill_profiles, noop_reverse),
    ]
