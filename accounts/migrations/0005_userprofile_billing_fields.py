"""Add Stripe + subscription state fields to UserProfile."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_merge_20260507_1006"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="subscription_tier",
            field=models.CharField(
                max_length=16,
                choices=[
                    ("sniffer", "Sniffer (Free)"),
                    ("exploit", "Exploit"),
                    ("zeroday", "Zero Day"),
                ],
                default="sniffer",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="subscription_status",
            field=models.CharField(
                max_length=16,
                choices=[
                    ("none",     "None"),
                    ("active",   "Active"),
                    ("trialing", "Trialing"),
                    ("past_due", "Past due"),
                    ("canceled", "Canceled"),
                    ("unpaid",   "Unpaid"),
                ],
                default="none",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="stripe_customer_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="stripe_subscription_id",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="current_period_end",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
