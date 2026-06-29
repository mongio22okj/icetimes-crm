from django.db import migrations


REMAP = {
    "inviato": "nuovo",
    "registrato": "nuovo",
    "kyc": "nuovo",
    "retained": "ftd",
    "rifiutato": "not_interested",
}


def forward(apps, schema_editor):
    Lead = apps.get_model("tracking", "Lead")
    for old, new in REMAP.items():
        Lead.objects.filter(stage=old).update(stage=new)


def backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("tracking", "0016_alter_lead_stage"),
    ]
    operations = [
        migrations.RunPython(forward, backward),
    ]
