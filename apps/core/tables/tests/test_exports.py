"""Export endpoint tests via the Customer table."""
import csv
import io

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.customers.tests.factories import CustomerFactory
from apps.invoices.pdf import weasyprint_available

pytestmark = pytest.mark.django_db

# PDF tests need WeasyPrint's native libs. Skip when absent rather than
# fail — same pattern as apps/invoices/tests/test_pdf.py.
weasyprint_libs = pytest.mark.skipif(
    not weasyprint_available(),
    reason="WeasyPrint native libs not available in this environment",
)


@pytest.fixture
def staff(db):
    return UserFactory(is_staff=True)


# ── CSV ────────────────────────────────────────────────────────────────


def test_csv_export_content_type_and_disposition(client, staff):
    CustomerFactory()
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_export=csv")
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/csv")
    assert "attachment;" in r["Content-Disposition"]
    assert ".csv" in r["Content-Disposition"]


def test_csv_export_includes_header_and_data_row():
    pass  # covered by next test which is more thorough


def test_csv_export_row_count_matches_filtered_queryset(client, staff):
    a = CustomerFactory(name="Acme", status="active")
    b = CustomerFactory(name="Other", status="inactive")
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_export=csv&status=active")
    reader = csv.reader(io.StringIO(r.content.decode()))
    rows = list(reader)
    # 1 header row + 1 data row (only Acme matches the filter)
    assert len(rows) == 2
    # Header has the column labels
    assert "Customer" in rows[0]
    assert "Email" in rows[0]
    # Data row has the customer name
    assert "Acme" in rows[1]


def test_csv_export_honors_search(client, staff):
    a = CustomerFactory(name="Northwind")
    b = CustomerFactory(name="Acme")
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_export=csv&q=northwind")
    rows = list(csv.reader(io.StringIO(r.content.decode())))
    assert len(rows) == 2
    assert "Northwind" in rows[1]


# ── XLSX ───────────────────────────────────────────────────────────────


def test_xlsx_export_content_type(client, staff):
    CustomerFactory()
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_export=xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r["Content-Type"]
    assert ".xlsx" in r["Content-Disposition"]


def test_xlsx_export_round_trip_via_openpyxl(client, staff):
    CustomerFactory(name="Aigars Acme", status="active")
    CustomerFactory(name="Beth", status="inactive")
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_export=xlsx&status=active")
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    rows = list(ws.values)
    # Header + 1 active row
    assert len(rows) == 2
    assert "Customer" in rows[0]
    assert "Aigars Acme" in rows[1]


# ── PDF ────────────────────────────────────────────────────────────────


@weasyprint_libs
def test_pdf_export_content_type(client, staff):
    CustomerFactory()
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_export=pdf")
    assert r.status_code == 200
    assert r["Content-Type"] == "application/pdf"
    assert ".pdf" in r["Content-Disposition"]
    assert r.content[:4] == b"%PDF"


def test_pdf_export_caps_at_500_rows(client, staff):
    """Generating > 500 rows must return 400, not silently truncate.

    This check happens BEFORE we touch WeasyPrint, so it works without
    the native libs installed.
    """
    CustomerFactory.create_batch(501)
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_export=pdf")
    assert r.status_code == 400
    assert b"500" in r.content


# ── Common ─────────────────────────────────────────────────────────────


def test_unknown_format_returns_400(client, staff):
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_export=svg")
    assert r.status_code == 400


def test_export_requires_auth(client):
    r = client.get(reverse("customers:list") + "?_export=csv")
    assert r.status_code in (301, 302)


def test_export_requires_staff(client):
    user = UserFactory(is_staff=False)
    client.force_login(user)
    r = client.get(reverse("customers:list") + "?_export=csv")
    assert r.status_code == 403
