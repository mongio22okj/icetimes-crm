from datetime import date

import pytest

from apps.customers.tests.factories import CustomerFactory
from apps.invoices.forms import InvoiceForm, InvoiceItemFormSet
from apps.invoices.tests.factories import InvoiceFactory

pytestmark = pytest.mark.django_db


def _base_payload(customer, **overrides):
    payload = {
        "customer": customer.pk,
        "order": "",
        "issue_date": date(2026, 6, 1).isoformat(),
        "due_date": date(2026, 6, 30).isoformat(),
        "tax_rate": "10.00",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def test_invoice_form_valid_minimal():
    c = CustomerFactory()
    form = InvoiceForm(data=_base_payload(c))
    assert form.is_valid(), form.errors


def test_due_date_before_issue_date_rejected():
    c = CustomerFactory()
    form = InvoiceForm(data=_base_payload(
        c,
        issue_date=date(2026, 6, 30).isoformat(),
        due_date=date(2026, 6, 1).isoformat(),
    ))
    assert not form.is_valid()
    assert "Due date cannot be before issue date." in str(form.errors)


# ----- Formset -----

def _formset_payload(prefix="items", *, rows):
    """Build formset management + row payload."""
    data = {
        f"{prefix}-TOTAL_FORMS": str(len(rows)),
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "1",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for i, row in enumerate(rows):
        for key, value in row.items():
            data[f"{prefix}-{i}-{key}"] = value
    return data


def test_formset_with_one_valid_row_accepted():
    inv = InvoiceFactory()
    data = _formset_payload(rows=[{
        "description": "Consulting",
        "quantity": "2",
        "unit_price": "150.00",
    }])
    fs = InvoiceItemFormSet(data, instance=inv)
    assert fs.is_valid(), fs.errors


def test_formset_with_zero_rows_rejected():
    inv = InvoiceFactory()
    data = _formset_payload(rows=[])
    fs = InvoiceItemFormSet(data, instance=inv)
    assert not fs.is_valid()


def test_formset_negative_quantity_rejected():
    inv = InvoiceFactory()
    data = _formset_payload(rows=[{
        "description": "Bad row",
        "quantity": "-1",
        "unit_price": "10.00",
    }])
    fs = InvoiceItemFormSet(data, instance=inv)
    assert not fs.is_valid()
