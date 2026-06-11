"""Global search — JSON endpoint queried by the command palette.

Searches across Customers, Invoices, Products, Orders, Mail, and
Kanban cards. Owner/staff-scoped, returns at most 5 results per
group plus a count badge.
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse


@login_required
def global_search(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"q": q, "groups": []})

    user = request.user
    groups = []

    # Customers — staff only
    if user.is_staff:
        from apps.customers.models import Customer
        customers = list(
            Customer.objects.filter(
                Q(name__icontains=q) | Q(email__icontains=q) | Q(company__icontains=q)
            )[:5]
        )
        if customers:
            groups.append({
                "label": "Customers",
                "icon": "user-plus",
                "items": [
                    {
                        "label": c.name,
                        "subtitle": c.email or c.company or "",
                        "url": reverse("customers:detail", args=[c.pk]),
                    }
                    for c in customers
                ],
            })

    # Invoices — staff only
    if user.is_staff:
        from apps.invoices.models import Invoice
        invoices = list(
            Invoice.objects.filter(
                Q(number__icontains=q) | Q(customer__name__icontains=q)
            ).select_related("customer")[:5]
        )
        if invoices:
            groups.append({
                "label": "Invoices",
                "icon": "file-text",
                "items": [
                    {
                        "label": inv.number,
                        "subtitle": f"{inv.customer.name} · {inv.get_status_display()}",
                        "url": reverse("invoices:detail", args=[inv.pk]),
                    }
                    for inv in invoices
                ],
            })

    # Products
    from apps.products.models import Product
    products = list(
        Product.objects.filter(
            Q(name__icontains=q) | Q(description__icontains=q)
        )[:5]
    )
    if products:
        groups.append({
            "label": "Products",
            "icon": "package",
            "items": [
                {
                    "label": p.name,
                    "subtitle": f"${p.price}" if hasattr(p, "price") else "",
                    "url": reverse("products:detail", args=[p.pk]),
                }
                for p in products
            ],
        })

    # Orders
    from apps.orders.models import Order
    orders = list(
        Order.objects.filter(
            Q(number__icontains=q) | Q(customer__name__icontains=q)
        ).select_related("customer")[:5]
    )
    if orders:
        groups.append({
            "label": "Orders",
            "icon": "shopping-cart",
            "items": [
                {
                    "label": o.number or f"Order #{o.pk}",
                    "subtitle": f"{o.customer.name} · {o.get_status_display()}",
                    "url": reverse("orders:detail", args=[o.pk]),
                }
                for o in orders
            ],
        })

    # Mail (only my own messages — sender or recipient)
    if user.is_staff:
        from apps.mail.models import Message
        messages_qs = list(
            Message.objects.filter(
                Q(subject__icontains=q) | Q(body__icontains=q),
            ).filter(
                Q(sender=user) | Q(recipient=user),
            ).select_related("sender", "recipient").order_by("-sent_at", "-created_at")[:5]
        )
        if messages_qs:
            groups.append({
                "label": "Mail",
                "icon": "mail",
                "items": [
                    {
                        "label": m.subject or "(no subject)",
                        "subtitle": f"{m.sender.username} → {m.recipient.username}",
                        "url": reverse("mail:thread", args=[m.pk]),
                    }
                    for m in messages_qs
                ],
            })

    # Kanban cards
    if user.is_staff:
        from apps.kanban.models import Card
        cards = list(
            Card.objects.filter(
                Q(title__icontains=q) | Q(description__icontains=q)
            )[:5]
        )
        if cards:
            groups.append({
                "label": "Kanban",
                "icon": "trello",
                "items": [
                    {
                        "label": card.title,
                        "subtitle": card.get_status_display(),
                        "url": reverse("kanban:detail", args=[card.pk]),
                    }
                    for card in cards
                ],
            })

    return JsonResponse({"q": q, "groups": groups})
