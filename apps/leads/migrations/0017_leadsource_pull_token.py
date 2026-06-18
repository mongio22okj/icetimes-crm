from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0016_lead_meta_tiktok_clids"),
    ]

    operations = [
        migrations.AddField(
            model_name="leadsource",
            name="pull_token",
            field=models.CharField(
                "Pull x-api-key",
                blank=True,
                max_length=255,
                help_text=(
                    "Solo TrackBox: chiave x-api-key per la PULL "
                    "(stati/depositi), DIVERSA da quella di push in `token`. "
                    "Specifica per broker."
                ),
            ),
        ),
    ]
