"""Initial migration for the accounts app — adds ActivityEvent."""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[
                    ("login", "Login"),
                    ("login_failed", "Login failed"),
                    ("logout", "Logout"),
                    ("signup", "Signup"),
                    ("password_change", "Password change"),
                    ("password_reset", "Password reset"),
                    ("profile_update", "Profile update"),
                    ("conversation_delete", "Conversation deleted"),
                    ("conversation_rename", "Conversation renamed"),
                    ("conversation_export", "Conversation exported"),
                    ("subscription_activate", "Subscription activated"),
                ], max_length=40)),
                ("detail", models.CharField(blank=True, default="", max_length=255)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.deletion.CASCADE,
                    related_name="activity_events",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="activityevent",
            index=models.Index(fields=["user", "-created_at"], name="accounts_ac_user_id_e9f3b9_idx"),
        ),
    ]
