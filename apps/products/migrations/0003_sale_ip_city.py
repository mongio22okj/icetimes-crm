from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_landing_fields_and_sale"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="ip",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sale",
            name="city",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
