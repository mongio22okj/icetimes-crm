from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0006_product_landing_sections"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="nav_name",
            field=models.CharField(blank=True, max_length=120,
                                   help_text="Nome mostrato nella nav e nel titolo della landing."),
        ),
        migrations.AddField(
            model_name="product",
            name="logo",
            field=models.ImageField(blank=True, null=True, upload_to="products/logos/",
                                    verbose_name="Logo landing"),
        ),
    ]
