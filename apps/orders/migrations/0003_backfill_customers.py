from django.db import migrations


def forward(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Customer = apps.get_model("customers", "Customer")

    user_to_customer = {}  # user_id -> customer_id

    for order in Order.objects.select_related("customer").all():
        user = order.customer
        if user is None:
            continue
        if user.id not in user_to_customer:
            email = (user.email or f"{user.username}@apex.local").strip().lower()
            full_name = f"{user.first_name} {user.last_name}".strip() or user.username
            # Historical migration models don't carry custom managers, so
            # Customer.objects here is the plain default (no SoftDelete filtering).
            customer, _ = Customer.objects.get_or_create(
                email=email,
                defaults={"name": full_name, "status": "active"},
            )
            user_to_customer[user.id] = customer.id
        order.customer_new_id = user_to_customer[user.id]
        order.save(update_fields=["customer_new_id"])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_add_customer_fk_temp"),
    ]

    operations = [
        migrations.RunPython(forward, reverse_noop),
    ]
