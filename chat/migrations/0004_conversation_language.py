"""Add language ('asm' | 'c') to Conversation."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0003_message_token_counts"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="language",
            field=models.CharField(
                choices=[("asm", "Assembly"), ("c", "C")],
                default="asm",
                max_length=8,
            ),
        ),
    ]
