from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.invoices.models import InvalidTransition
from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory

pytestmark = pytest.mark.django_db


# ----- Numbering -----

def test_first_invoice_of_year_gets_0001():
    inv = InvoiceFactory(issue_date=date(2026, 6, 1))
    assert inv.number == "INV-2026-0001"


def test_second_invoice_of_year_gets_0002():
    InvoiceFactory(issue_date=date(2026, 6, 1))
    second = InvoiceFactory(issue_date=date(2026, 8, 1))
    assert second.number == "INV-2026-0002"


def test_new_year_resets_sequence():
    InvoiceFactory(issue_date=date(2026, 12, 31))
    next_year = InvoiceFactory(issue_date=date(2027, 1, 1))
    assert next_year.number == "INV-2027-0001"


def test_number_is_immutable_after_create():
    inv = InvoiceFactory()
    original = inv.number
    inv.notes = "edited"
    inv.save()
    inv.refresh_from_db()
    assert inv.number == original


# ----- Totals -----

def test_subtotal_sums_item_amounts():
    inv = InvoiceFactory(tax_rate=Decimal("0"))
    InvoiceItemFactory(invoice=inv, quantity=2, unit_price=Decimal("10.00"))
    InvoiceItemFactory(invoice=inv, quantity=3, unit_price=Decimal("5.50"))
    assert inv.subtotal == Decimal("36.50")


def test_tax_amount_is_rate_percent_of_subtotal():
    inv = InvoiceFactory(tax_rate=Decimal("10"))
    InvoiceItemFactory(invoice=inv, quantity=1, unit_price=Decimal("100.00"))
    assert inv.tax_amount == Decimal("10.00")


def test_total_equals_subtotal_plus_tax():
    inv = InvoiceFactory(tax_rate=Decimal("10"))
    InvoiceItemFactory(invoice=inv, quantity=1, unit_price=Decimal("100.00"))
    assert inv.total == Decimal("110.00")


# ----- Derived status -----

def test_overdue_when_sent_and_past_due():
    inv = InvoiceFactory(status="draft",
                         due_date=timezone.now().date() - timedelta(days=1))
    inv.mark_sent()
    assert inv.is_overdue is True
    assert inv.display_status == "overdue"


def test_not_overdue_when_draft():
    inv = InvoiceFactory(status="draft",
                         due_date=timezone.now().date() - timedelta(days=1))
    assert inv.is_overdue is False
    assert inv.display_status == "draft"


def test_not_overdue_when_paid():
    inv = InvoiceFactory(due_date=timezone.now().date() - timedelta(days=1))
    inv.mark_sent()
    inv.mark_paid()
    assert inv.is_overdue is False
    assert inv.display_status == "paid"


# ----- State machine -----

def test_mark_sent_from_draft_succeeds():
    inv = InvoiceFactory(status="draft")
    inv.mark_sent()
    assert inv.status == "sent"
    assert inv.sent_at is not None


def test_mark_sent_from_sent_raises():
    inv = InvoiceFactory(status="draft")
    inv.mark_sent()
    with pytest.raises(InvalidTransition):
        inv.mark_sent()


def test_mark_paid_from_draft_raises():
    inv = InvoiceFactory(status="draft")
    with pytest.raises(InvalidTransition):
        inv.mark_paid()


def test_mark_paid_from_sent_succeeds():
    inv = InvoiceFactory(status="draft")
    inv.mark_sent()
    inv.mark_paid()
    assert inv.status == "paid"
    assert inv.paid_at is not None


def test_mark_void_from_sent_succeeds():
    inv = InvoiceFactory(status="draft")
    inv.mark_sent()
    inv.mark_void()
    assert inv.status == "void"
    assert inv.voided_at is not None


def test_paid_is_terminal():
    inv = InvoiceFactory(status="draft")
    inv.mark_sent()
    inv.mark_paid()
    with pytest.raises(InvalidTransition):
        inv.mark_void()


# ----- Public token -----

def test_public_token_assigned_on_create():
    inv = InvoiceFactory()
    assert inv.public_token is not None


def test_public_token_is_unique():
    a = InvoiceFactory()
    b = InvoiceFactory()
    assert a.public_token != b.public_token
