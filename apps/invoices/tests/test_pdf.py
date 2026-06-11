"""PDF rendering tests.

Skipped locally when WeasyPrint's native libs (cairo/pango/gdk-pixbuf)
aren't installed. Install with:
  - macOS: brew install cairo pango gdk-pixbuf libffi
  - Debian: apt-get install libpango-1.0-0 libpangoft2-1.0-0
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.invoices.pdf import weasyprint_available
from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory

pytestmark = pytest.mark.django_db

weasyprint_libs = pytest.mark.skipif(
    not weasyprint_available(),
    reason="WeasyPrint native libs (cairo/pango/gdk-pixbuf) not installed",
)


# ----- Always-on: code surface works even without native libs -----

def test_pdf_view_requires_staff(client):
    """No libs needed: StaffRequiredMixin rejects before the import."""
    user = UserFactory(is_staff=False)
    client.force_login(user)
    inv = InvoiceFactory()
    r = client.get(reverse("invoices:pdf", args=[inv.pk]))
    assert r.status_code == 403


def test_pdf_view_requires_login(client):
    inv = InvoiceFactory()
    r = client.get(reverse("invoices:pdf", args=[inv.pk]))
    assert r.status_code == 302
    assert "login" in r.url


# ----- Gated on native libs -----

@weasyprint_libs
def test_render_invoice_pdf_returns_pdf_bytes():
    from apps.invoices.pdf import render_invoice_pdf
    inv = InvoiceFactory()
    InvoiceItemFactory(invoice=inv, quantity=2, unit_price=Decimal("25.00"))
    pdf = render_invoice_pdf(inv)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000


@weasyprint_libs
def test_pdf_view_returns_pdf_attachment(client):
    user = UserFactory(is_staff=True)
    client.force_login(user)
    inv = InvoiceFactory()
    InvoiceItemFactory(invoice=inv)
    r = client.get(reverse("invoices:pdf", args=[inv.pk]))
    assert r.status_code == 200
    assert r["Content-Type"] == "application/pdf"
    assert inv.number in r["Content-Disposition"]
    assert r.content[:4] == b"%PDF"
