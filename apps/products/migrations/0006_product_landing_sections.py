from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0005_product_media"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="facts_table",
            field=models.JSONField(blank=True, default=list,
                                   help_text='Es: [{"icon":"📊","label":"Tipo","value":"Robot AI"}]'),
        ),
        migrations.AddField(
            model_name="product",
            name="features_list",
            field=models.JSONField(blank=True, default=list,
                                   help_text='Es: [{"icon_type":"bolt","title":"Algoritmi","body":"..."}]'),
        ),
        migrations.AddField(
            model_name="product",
            name="features_desc",
            field=models.TextField(blank=True,
                                   help_text="Testo introduttivo sezione Caratteristiche."),
        ),
        migrations.AddField(
            model_name="product",
            name="steps_list",
            field=models.JSONField(blank=True, default=list,
                                   help_text='Es: [{"label":"Primo passo","title":"Registrazione","body":"..."}]'),
        ),
        migrations.AddField(
            model_name="product",
            name="faq_list",
            field=models.JSONField(blank=True, default=list,
                                   help_text='Es: [{"q":"Domanda?","a":"Risposta."}]'),
        ),
    ]
