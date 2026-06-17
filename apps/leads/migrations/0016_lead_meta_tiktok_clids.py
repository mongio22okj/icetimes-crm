from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0015_lead_gclid_gads_uploaded_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="fbclid",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=255,
                help_text=(
                    "Meta (Facebook/Instagram) click id. Per attribuzione e "
                    "invio conversioni via Conversions API (CAPI)."
                ),
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="ttclid",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=255,
                help_text=(
                    "TikTok click id. Per attribuzione e invio conversioni "
                    "via TikTok Events API."
                ),
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="meta_uploaded_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="Quando la conversione è stata inviata a Meta (CAPI). Null = non ancora.",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="tiktok_uploaded_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="Quando la conversione è stata inviata a TikTok (Events API). Null = non ancora.",
            ),
        ),
    ]
