import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Lead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(db_index=True,
                                                    default=django.utils.timezone.now)),
                ("event_at", models.DateTimeField(
                    blank=True, null=True,
                    help_text="Timestamp riportato da TrackBox, se presente nel postback.")),
                ("uniqueid", models.CharField(blank=True, db_index=True, max_length=128)),
                ("firstname", models.CharField(blank=True, max_length=120)),
                ("lastname", models.CharField(blank=True, max_length=120)),
                ("email", models.EmailField(blank=True, db_index=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("country", models.CharField(blank=True, max_length=8)),
                ("status", models.CharField(blank=True, max_length=120)),
                ("is_deposit", models.BooleanField(default=False)),
                ("source", models.CharField(default="postback", max_length=32)),
                ("payload", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
