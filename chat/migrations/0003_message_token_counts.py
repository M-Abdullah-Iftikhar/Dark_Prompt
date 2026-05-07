"""Add prompt_tokens / completion_tokens to Message."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0002_conversation_is_pinned"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="prompt_tokens",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="completion_tokens",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
