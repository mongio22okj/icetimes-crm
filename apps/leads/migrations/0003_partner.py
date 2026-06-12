import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0002_leadsource"),
    ]

    operations = [
        migrations.CreateModel(
            name="Partner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(help_text="Univoco, caratteri latini (lettere, numeri, underscore, trattini).", max_length=80, unique=True, verbose_name="ID Partner")),
                ("name", models.CharField(help_text='Nome visualizzato. Es. "Partner #1".', max_length=200, verbose_name="Nome")),
                ("landing_url", models.URLField(blank=True, help_text="URL della landing del partner (esterna).", verbose_name="URL della landing")),
                ("api_key", models.CharField(blank=True, help_text="Opzionale — solo se il partner richiede una API key per gli invii.", max_length=255, verbose_name="Chiave API")),
                ("note", models.TextField(blank=True, help_text="Promemoria interno. Non viene mostrato pubblicamente.", verbose_name="Nota")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
