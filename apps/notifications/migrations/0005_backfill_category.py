"""Back-fill `Notification.category` for rows created before Phase 13.

Pre-existing rows have `category=""` because the field was just added
with `default="system"` in 0004. We re-derive it from `kind` so the
filter pills on /notifications/ partition the existing data correctly.
"""
from django.db import migrations

KIND_TO_CATEGORY = {
    "invoice_sent": "billing",
    "invoice_paid": "billing",
    "invoice_void": "billing",
    "order_placed": "system",
    "new_mail":     "mention",
    "new_chat":     "mention",
}


def forwards(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    for kind, category in KIND_TO_CATEGORY.items():
        Notification.objects.filter(kind=kind).update(category=category)


def backwards(apps, schema_editor):
    # No-op: the column persists; reverting just leaves it populated.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0004_notificationpreference_pushsubscription_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
