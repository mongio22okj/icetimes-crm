from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0003_sale_ip_city"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="device",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
