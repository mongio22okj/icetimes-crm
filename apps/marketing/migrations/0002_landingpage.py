import django.utils.timezone
from django.db import migrations, models


def seed_default_landings(apps, schema_editor):
    """Seed two landings that match the URLs previously hardcoded
    (/landing/newsletter/, /landing/trading/) so old links keep working."""
    LandingPage = apps.get_model("marketing", "LandingPage")
    LandingPage.objects.get_or_create(
        slug="newsletter",
        defaults={
            "title": "Resta aggiornato",
            "subtitle": "Ricevi le novità una volta a settimana. Niente spam.",
            "badge": "📬",
            "cta_label": "Iscrivimi",
            "theme": "dark",
            "accent_color": "#6366f1",
            "form_variant": "email",
            "funnel": "newsletter",
            "source_tag": "newsletter",
            "sub": "",
            "success_message": "Iscrizione confermata! Riceverai presto le novità.",
            "redirect_url": "",
            "is_active": True,
        },
    )
    LandingPage.objects.get_or_create(
        slug="trading",
        defaults={
            "title": "Inizia a fare trading oggi",
            "subtitle": "Compila il form e un nostro consulente ti contatterà entro 1 ora.",
            "badge": "🔥 OFFERTA LIMITATA",
            "cta_label": "Accedi ora",
            "theme": "light",
            "accent_color": "#f59e0b",
            "form_variant": "full",
            "funnel": "trading-2026-A",
            "source_tag": "direct",
            "sub": "",
            "success_message": "Grazie! Ti contatteremo entro 1 ora.",
            "redirect_url": "",
            "is_active": True,
        },
    )


def unseed_default_landings(apps, schema_editor):
    LandingPage = apps.get_model("marketing", "LandingPage")
    LandingPage.objects.filter(slug__in=["newsletter", "trading"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("marketing", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LandingPage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=80, unique=True, help_text="Parte finale dell'URL. Es. \"trading-2026-A\".")),
                ("title", models.CharField(max_length=200)),
                ("subtitle", models.CharField(blank=True, max_length=300)),
                ("badge", models.CharField(blank=True, help_text="Mini-badge sopra il titolo, es. \"🔥 OFFERTA LIMITATA\".", max_length=80)),
                ("cta_label", models.CharField(default="Accedi ora", help_text="Testo del bottone di invio.", max_length=60)),
                ("theme", models.CharField(choices=[("light", "Chiaro"), ("dark", "Scuro")], default="light", max_length=10)),
                ("accent_color", models.CharField(default="#f59e0b", help_text="Colore esadecimale del bottone (es. #6366f1, #10b981).", max_length=20)),
                ("form_variant", models.CharField(choices=[("full", "Form completo (nome, cognome, email, telefono, paese)"), ("email", "Solo email")], default="full", max_length=10)),
                ("funnel", models.CharField(blank=True, help_text="Nome funnel/campagna. Es. \"trading-2026-A\".", max_length=120)),
                ("source_tag", models.CharField(blank=True, help_text="Canale, es. FB, GoogleAds, TikTok.", max_length=64, verbose_name="Source")),
                ("sub", models.CharField(blank=True, help_text="ID ad set / keyword / sub-id.", max_length=120)),
                ("success_message", models.CharField(default="Grazie! Ti contatteremo presto.", help_text="Mostrato dopo l'invio quando NON c'è redirect.", max_length=200)),
                ("redirect_url", models.URLField(blank=True, help_text="Se impostato, il browser viene reindirizzato qui dopo l'invio.")),
                ("is_active", models.BooleanField(default=True, help_text="Se OFF, la URL pubblica risponde 404.")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(seed_default_landings, unseed_default_landings),
    ]
