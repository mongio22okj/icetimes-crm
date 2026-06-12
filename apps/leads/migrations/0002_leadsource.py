import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lead",
            name="source",
            field=models.CharField(default="postback", max_length=64),
        ),
        migrations.CreateModel(
            name="LeadSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("kind", models.CharField(max_length=20, choices=[
                    ("trackbox", "TrackBox"), ("irev", "IREV"),
                    ("affinitrax", "Affinitrax"),
                    ("v3", "Integration v3 (api_token)")])),
                ("base_url", models.URLField(help_text="Es. https://stylishwnt.com")),
                ("is_active", models.BooleanField(default=True)),
                ("token", models.CharField(blank=True, max_length=255,
                                           verbose_name="Token / API key")),
                ("username", models.CharField(blank=True, max_length=120,
                                              help_text="Solo TrackBox")),
                ("password", models.CharField(blank=True, max_length=255,
                                              help_text="Solo TrackBox")),
                ("ai", models.CharField(blank=True, max_length=64,
                                        help_text="Solo TrackBox", verbose_name="ai")),
                ("ci", models.CharField(blank=True, default="1", max_length=64,
                                        help_text="Solo TrackBox", verbose_name="ci")),
                ("gi", models.CharField(blank=True, max_length=64,
                                        help_text="Solo TrackBox", verbose_name="gi")),
                ("affiliate_id", models.CharField(blank=True, max_length=64,
                                                  help_text="Solo IREV")),
                ("offer_id", models.CharField(blank=True, max_length=64,
                                              help_text="IREV / Affinitrax")),
                ("goal_lead", models.CharField(blank=True, max_length=64,
                                               help_text="Solo IREV",
                                               verbose_name="Goal UUID lead")),
                ("goal_ftd", models.CharField(blank=True, max_length=64,
                                              help_text="Solo IREV",
                                              verbose_name="Goal UUID FTD")),
                ("link_id", models.CharField(blank=True, max_length=64,
                                             help_text="Solo Integration v3")),
                ("funnel", models.CharField(blank=True, max_length=120,
                                            help_text="Solo Integration v3")),
                ("source_tag", models.CharField(blank=True, max_length=64,
                                                help_text="Solo Integration v3 (es. FB)",
                                                verbose_name="Source")),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
    ]
