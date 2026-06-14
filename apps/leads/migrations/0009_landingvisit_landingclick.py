from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0008_syncaudit"),
    ]

    operations = [
        migrations.CreateModel(
            name="LandingVisit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_id", models.CharField(db_index=True, max_length=255)),
                ("page", models.CharField(max_length=255)),
                ("utm_source", models.CharField(blank=True, max_length=255, null=True)),
                ("utm_campaign", models.CharField(blank=True, max_length=255, null=True)),
                ("utm_medium", models.CharField(blank=True, max_length=255, null=True)),
                ("utm_content", models.CharField(blank=True, max_length=255, null=True)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="LandingClick",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_id", models.CharField(db_index=True, max_length=255)),
                ("button_name", models.CharField(max_length=255)),
                ("page", models.CharField(max_length=255)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
