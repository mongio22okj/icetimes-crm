import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0003_partner"),
    ]

    operations = [
        migrations.CreateModel(
            name="Campaign",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="Nome campagna")),
                ("platform", models.CharField(choices=[("facebook", "Facebook Ads"), ("google", "Google Ads"), ("tiktok", "TikTok Ads"), ("instagram", "Instagram Ads"), ("linkedin", "LinkedIn Ads"), ("other", "Altro")], default="facebook", max_length=20, verbose_name="Piattaforma")),
                ("budget", models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name="Budget (€)")),
                ("spent", models.DecimalField(decimal_places=2, default=0, help_text="Spesa totale ad oggi su questa campagna.", max_digits=12, verbose_name="Spesa (€)")),
                ("clicks", models.PositiveIntegerField(default=0)),
                ("leads_count", models.PositiveIntegerField(default=0, help_text="Lead ricevuti dalla campagna. Aggiornabile manualmente o (futuro) calcolabile via funnel/source tracking.", verbose_name="Lead")),
                ("status", models.CharField(choices=[("active", "Attiva"), ("paused", "In pausa"), ("completed", "Completata")], db_index=True, default="active", max_length=20)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
