from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_emails(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    seen = set()
    now = timezone.now()
    for u in User.objects.order_by("pk"):
        email = (u.email or "").strip().lower()
        if not email:
            email = f"{u.username}@apex.local"
        if email in seen:
            email = f"{u.username}+{u.pk}@apex.local"
        u.email = email
        seen.add(email)
        if not u.email_verified_at:
            u.email_verified_at = now
        u.save(update_fields=["email", "email_verified_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_twofactordevice"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_emails, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(max_length=254, unique=True),
        ),
    ]
