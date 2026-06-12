from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="badge",
            field=models.CharField(blank=True, help_text='Mini-badge sopra il titolo, es. "🔥 OFFERTA LIMITATA".', max_length=80),
        ),
        migrations.AddField(
            model_name="product",
            name="cta_label",
            field=models.CharField(default="Acquista ora", help_text="Testo del bottone di acquisto.", max_length=60),
        ),
        migrations.AddField(
            model_name="product",
            name="accent_color",
            field=models.CharField(default="#f59e0b", help_text="Colore esadecimale del bottone (es. #6366f1, #10b981).", max_length=20),
        ),
        migrations.AddField(
            model_name="product",
            name="theme",
            field=models.CharField(choices=[("light", "Chiaro"), ("dark", "Scuro")], default="light", max_length=10),
        ),
        migrations.AddField(
            model_name="product",
            name="success_message",
            field=models.CharField(default="Grazie! Ti contatteremo presto.", help_text="Mostrato dopo l'invio quando NON c'è redirect.", max_length=200),
        ),
        migrations.AddField(
            model_name="product",
            name="redirect_url",
            field=models.URLField(blank=True, help_text="Se impostato, redirect alla URL dopo l'invio."),
        ),
        migrations.AddField(
            model_name="product",
            name="status_api_url",
            field=models.URLField(blank=True, help_text="Endpoint che riceve POST quando una Sale viene marcata sold/lost. Vuoto = nessuna notifica esterna.", verbose_name="URL API status"),
        ),
        migrations.AddField(
            model_name="product",
            name="status_api_key",
            field=models.CharField(blank=True, help_text="Inviata in header X-API-Key e nel body come api_key.", max_length=255, verbose_name="Chiave API status"),
        ),
        migrations.CreateModel(
            name="Sale",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("firstname", models.CharField(max_length=120)),
                ("lastname", models.CharField(max_length=120)),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("country", models.CharField(blank=True, default="IT", max_length=8)),
                ("status", models.CharField(choices=[("pending", "In attesa"), ("sold", "Venduto"), ("lost", "Mancato acquisto")], db_index=True, default="pending", max_length=16)),
                ("sold_at", models.DateTimeField(blank=True, null=True)),
                ("api_response", models.JSONField(blank=True, default=dict, help_text="Ultima risposta della Product.status_api_url.")),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="sales", to="products.product")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
