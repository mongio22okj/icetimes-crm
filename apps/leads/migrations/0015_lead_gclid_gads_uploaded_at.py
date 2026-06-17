from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0014_leadsource_landing_custom_html"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="gclid",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=255,
                help_text=(
                    "Google Ads click id catturato dalla landing. Lega il "
                    "lead alla campagna/click e serve all'Offline Conversion "
                    "Import (invio FTD a Google)."
                ),
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="gads_uploaded_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text=(
                    "Quando la conversione è stata caricata su Google Ads "
                    "(null = non ancora). Evita invii duplicati."
                ),
            ),
        ),
    ]
