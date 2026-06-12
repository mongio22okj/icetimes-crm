from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0005_2026_best_practices"),
    ]

    operations = [
        migrations.AddField(
            model_name="leadsource",
            name="landing_active",
            field=models.BooleanField(
                default=False,
                help_text="Se ON, /b/<landing_slug>/ risponde con la landing del broker.",
                verbose_name="Landing pubblica attiva",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="landing_slug",
            field=models.SlugField(
                blank=True, max_length=80,
                help_text="URL: /b/<slug>/. Esempio: broker1-crypto.",
                verbose_name="Slug landing",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="landing_hero_title",
            field=models.CharField(
                blank=True, default="Inizia a investire oggi", max_length=200,
                verbose_name="Hero — titolo",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="landing_hero_subtitle",
            field=models.TextField(
                blank=True,
                default="La piattaforma più affidabile. Registrati in 2 minuti.",
                verbose_name="Hero — sottotitolo",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="landing_features",
            field=models.TextField(
                blank=True,
                help_text='Una feature per riga. Es: "Regolamentato CONSOB & CySEC".',
                verbose_name="Hero — features (1 per riga)",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="landing_trust_badges",
            field=models.TextField(
                blank=True,
                help_text='Badge piccoli sotto il form. Es: "SSL Sicuro", "GDPR", "4.8/5".',
                verbose_name="Trust badges (1 per riga)",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="landing_theme",
            field=models.CharField(
                choices=[("gradient", "Gradient viola/blu"), ("light", "Chiaro"), ("dark", "Scuro")],
                default="gradient", max_length=20,
                verbose_name="Tema",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="landing_accent_color",
            field=models.CharField(
                default="#667eea", max_length=20,
                help_text="Colore esadecimale del bottone CTA.",
                verbose_name="Colore accent",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="landing_cta_label",
            field=models.CharField(
                default="Crea Account Gratis", max_length=80,
                verbose_name="Label CTA",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="landing_redirect_url",
            field=models.URLField(
                blank=True,
                help_text="Vuoto = mostra messaggio inline.",
                verbose_name="Redirect post-submit",
            ),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="landing_success_message",
            field=models.CharField(
                default="Grazie! Ti contatteremo entro pochi minuti.",
                max_length=200,
                verbose_name="Messaggio successo",
            ),
        ),
    ]
