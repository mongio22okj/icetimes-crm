import secrets

from django.db import migrations, models


def backfill_webhook_tokens(apps, schema_editor):
    Partner = apps.get_model("leads", "Partner")
    for p in Partner.objects.filter(webhook_token=""):
        p.webhook_token = secrets.token_urlsafe(24)
        p.save(update_fields=["webhook_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0006_broker_landings"),
    ]

    operations = [
        migrations.AddField(
            model_name="partner",
            name="webhook_token",
            field=models.CharField(
                blank=True, max_length=64,
                help_text="Token segreto che il partner usa per fare POST a /in/<slug>/?token=<token>. Auto-generato al primo save.",
                verbose_name="Token postback (nostro)",
            ),
        ),
        migrations.AlterField(
            model_name="partner",
            name="api_key",
            field=models.CharField(
                blank=True, max_length=255,
                help_text="Opzionale — chiave API del partner, se serve per inviargli qualcosa.",
                verbose_name="Chiave API (loro)",
            ),
        ),
        migrations.RunPython(backfill_webhook_tokens, migrations.RunPython.noop),
    ]
