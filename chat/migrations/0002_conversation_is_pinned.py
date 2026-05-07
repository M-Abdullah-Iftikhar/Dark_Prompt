"""Add is_pinned flag to Conversation."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="is_pinned",
            field=models.BooleanField(default=False),
        ),
    ]
