import pytest

from apps.customers.forms import CustomerForm
from apps.customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


def test_form_rejects_duplicate_email_case_insensitive():
    CustomerFactory(email="alice@example.com")
    form = CustomerForm(data={
        "name": "Alice Two",
        "email": "Alice@EXAMPLE.com",
        "phone": "",
        "company": "",
        "address": "",
        "city": "",
        "country": "",
        "status": "active",
        "notes": "",
    })
    assert not form.is_valid()
    assert "email" in form.errors


def test_form_allows_unchanged_email_for_same_customer():
    c = CustomerFactory(email="alice@example.com")
    form = CustomerForm(data={
        "name": c.name,
        "email": "Alice@EXAMPLE.com",
        "phone": "",
        "company": "",
        "address": "",
        "city": "",
        "country": "",
        "status": "active",
        "notes": "",
    }, instance=c)
    assert form.is_valid(), form.errors


def test_form_uses_phase12_widgets():
    """Phase 12 rewrite: each field uses one of the apps.core.widgets."""
    from apps.core.widgets import (
        FloatingLabelInput,
        FloatingLabelTextarea,
        IconPrefixInput,
    )
    form = CustomerForm()
    assert isinstance(form.fields["name"].widget, FloatingLabelInput)
    assert isinstance(form.fields["email"].widget, IconPrefixInput)
    assert isinstance(form.fields["notes"].widget, FloatingLabelTextarea)


def test_form_requires_name_and_email():
    form = CustomerForm(data={"name": "", "email": ""})
    assert not form.is_valid()
    assert "name" in form.errors
    assert "email" in form.errors
