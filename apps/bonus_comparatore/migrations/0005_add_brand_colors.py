from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bonus_comparatore", "0004_bookmaker_logos"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookmaker",
            name="brand_color",
            field=models.CharField(
                blank=True,
                default="#111827",
                max_length=20,
                help_text="Colore di sfondo del banner (es. #ffffff per bianco).",
            ),
        ),
        migrations.AddField(
            model_name="bookmaker",
            name="cta_color",
            field=models.CharField(
                blank=True,
                default="#ffd600",
                max_length=20,
                help_text="Colore del bottone CTA nel banner.",
            ),
        ),
        migrations.AddField(
            model_name="bookmaker",
            name="cta_text_color",
            field=models.CharField(
                blank=True,
                default="#111111",
                max_length=20,
                help_text="Colore del testo nel bottone CTA.",
            ),
        ),
        migrations.AddField(
            model_name="bookmaker",
            name="brand_text_dark",
            field=models.BooleanField(
                default=False,
                help_text="Testo scuro sul banner. Spuntare per sfondi chiari (es. bianco).",
            ),
        ),
    ]
