from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0004_sale_device"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="video_url",
            field=models.URLField(blank=True, verbose_name="URL video",
                                  help_text="YouTube o Vimeo — es. https://youtu.be/xxxx."),
        ),
        migrations.AddField(
            model_name="product",
            name="gallery_image_1",
            field=models.ImageField(blank=True, null=True, upload_to="products/gallery/",
                                    verbose_name="Immagine galleria 1"),
        ),
        migrations.AddField(
            model_name="product",
            name="gallery_image_2",
            field=models.ImageField(blank=True, null=True, upload_to="products/gallery/",
                                    verbose_name="Immagine galleria 2"),
        ),
        migrations.AddField(
            model_name="product",
            name="gallery_image_3",
            field=models.ImageField(blank=True, null=True, upload_to="products/gallery/",
                                    verbose_name="Immagine galleria 3"),
        ),
    ]
