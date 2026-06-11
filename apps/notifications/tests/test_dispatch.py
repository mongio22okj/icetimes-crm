import pytest

from apps.accounts.tests.factories import UserFactory
from apps.notifications.dispatch import (
    notify_invoice_paid,
    notify_invoice_sent,
    notify_invoice_void,
)
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _baseline_users(db):
    """Two staff (both should receive) + one regular + one inactive staff (should not)."""
    UserFactory(is_staff=True, is_active=True, username="staff_a")
    UserFactory(is_staff=True, is_active=True, username="staff_b")
    UserFactory(is_staff=False, is_active=True, username="regular")
    UserFactory(is_staff=True, is_active=False, username="inactive_staff")


def test_notify_invoice_sent_creates_one_per_active_staff(db):
    from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory
    inv = InvoiceFactory()
    InvoiceItemFactory(invoice=inv)
    notify_invoice_sent(inv)
    notes = Notification.objects.filter(kind="invoice_sent")
    recipients = {n.recipient.username for n in notes}
    assert recipients == {"staff_a", "staff_b"}


def test_notify_invoice_sent_populates_fields():
    from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory
    inv = InvoiceFactory()
    InvoiceItemFactory(invoice=inv)
    notify_invoice_sent(inv)
    n = Notification.objects.filter(kind="invoice_sent").first()
    assert inv.number in n.title
    assert inv.customer.name in n.body
    assert n.url == inv.get_absolute_url()


def test_notify_invoice_paid_records_total():
    from decimal import Decimal

    from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory
    inv = InvoiceFactory(tax_rate=Decimal("10"))
    InvoiceItemFactory(invoice=inv, quantity=1, unit_price=Decimal("100.00"))
    notify_invoice_paid(inv)
    n = Notification.objects.filter(kind="invoice_paid").first()
    assert "$110.00" in n.body


def test_notify_invoice_void_fires():
    from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory
    inv = InvoiceFactory()
    InvoiceItemFactory(invoice=inv)
    notify_invoice_void(inv)
    assert Notification.objects.filter(kind="invoice_void").count() == 2  # 2 active staff


def test_notify_order_placed_fires_on_order_creation():
    """Order.save wires notify_order_placed; creating an Order triggers it."""
    from apps.orders.tests.factories import OrderFactory
    Notification.objects.filter(kind="order_placed").delete()
    order = OrderFactory()
    note_count = Notification.objects.filter(kind="order_placed").count()
    assert note_count == 2  # 2 active staff
    n = Notification.objects.filter(kind="order_placed").first()
    assert order.number in n.title


def test_notify_new_mail_targets_recipient_only():
    from apps.mail.tests.factories import MessageFactory
    from apps.notifications.dispatch import notify_new_mail

    Notification.objects.filter(kind="new_mail").delete()
    msg = MessageFactory()  # creates two new users (sender, recipient)
    notify_new_mail(msg)
    notes = Notification.objects.filter(kind="new_mail")
    # One row only — only the recipient
    assert notes.count() == 1
    n = notes.first()
    assert n.recipient == msg.recipient
    assert msg.subject in n.title
    assert n.url == f"/mail/{msg.pk}/"


def test_notify_new_chat_targets_recipient_only():
    from apps.chat.tests.factories import ChatMessageFactory
    from apps.notifications.dispatch import notify_new_chat

    Notification.objects.filter(kind="new_chat").delete()
    msg = ChatMessageFactory()  # creates two new users
    notify_new_chat(msg)
    notes = Notification.objects.filter(kind="new_chat")
    assert notes.count() == 1
    n = notes.first()
    assert n.recipient == msg.recipient
    assert n.url == f"/chat/{msg.sender_id}/"


def test_no_recipients_is_noop(db):
    # Deactivate all staff
    from django.contrib.auth import get_user_model

    from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory
    User = get_user_model()
    User.objects.filter(is_staff=True).update(is_active=False)

    inv = InvoiceFactory()
    InvoiceItemFactory(invoice=inv)
    notify_invoice_sent(inv)
    assert Notification.objects.count() == 0
