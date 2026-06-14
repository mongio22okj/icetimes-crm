from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0007_partner_webhook_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("action", models.CharField(default="sync", max_length=50)),
                ("source", models.CharField(blank=True, max_length=120)),
                ("processed", models.PositiveIntegerField(default=0)),
                ("created", models.PositiveIntegerField(default=0)),
                ("updated", models.PositiveIntegerField(default=0)),
                ("details", models.TextField(blank=True)),
            ],
            options={"ordering": ["-timestamp"], "verbose_name": "Sync Audit", "verbose_name_plural": "Sync Audits"},
        ),
    ]
