from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Broker",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("offer_url", models.URLField(max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Campaign",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("broker", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="campaigns", to="tracker.broker")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Click",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("referrer", models.TextField(blank=True)),
                ("lead_id", models.CharField(db_index=True, max_length=64, unique=True)),
                ("converted", models.BooleanField(default=False)),
                ("conversion_time", models.DateTimeField(blank=True, null=True)),
                ("click_time", models.DateTimeField(auto_now_add=True)),
                ("utm_source", models.CharField(blank=True, max_length=255, null=True)),
                ("utm_medium", models.CharField(blank=True, max_length=255, null=True)),
                ("utm_campaign", models.CharField(blank=True, max_length=255, null=True)),
                ("utm_term", models.CharField(blank=True, max_length=255, null=True)),
                ("utm_content", models.CharField(blank=True, max_length=255, null=True)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="clicks", to="tracker.campaign")),
            ],
            options={"ordering": ["-click_time"]},
        ),
    ]
