from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0017_leadsource_pull_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="leadsource",
            name="hub_id",
            field=models.CharField(
                "Hub id (bxc)", blank=True, max_length=64,
                help_text="Solo Hypernet — es. BX-…"),
        ),
        migrations.AddField(
            model_name="leadsource",
            name="vertical_id",
            field=models.CharField(
                "Vertical id (vtc)", blank=True, max_length=64,
                help_text="Solo Hypernet — es. VT-…"),
        ),
        migrations.AlterField(
            model_name="leadsource",
            name="kind",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("trackbox", "TrackBox"),
                    ("irev", "IREV"),
                    ("affinitrax", "Affinitrax"),
                    ("v3", "Integration v3 (api_token)"),
                    ("hypernet", "Hypernet (HTN-AFF-SDK)"),
                    ("mediafront", "Mediafront (Midas)"),
                    ("spmmonster", "SPM Monster"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="leadsource",
            name="funnel",
            field=models.CharField(
                blank=True, max_length=120,
                help_text="Integration v3 / Hypernet"),
        ),
    ]
