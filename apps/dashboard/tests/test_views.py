import pytest

from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_dashboard_redirects_anon_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/accounts/login" in response.url


@pytest.mark.django_db
def test_dashboard_renders_for_authed_user(client):
    client.force_login(UserFactory())
    response = client.get("/")
    assert response.status_code == 200
    assert b"Dashboard" in response.content
    assert b"Lead totali" in response.content
    assert b"FTD" in response.content


@pytest.mark.django_db
def test_dashboard_kpis_in_context(client):
    client.force_login(UserFactory())
    response = client.get("/")
    kpis = response.context["kpis"]
    assert len(kpis) == 4
    assert {"label", "value", "icon", "accent"} <= set(kpis[0].keys())
    labels = {k["label"] for k in kpis}
    assert {"Lead totali", "FTD", "Conversione", "Broker attivi"} <= labels


@pytest.mark.django_db
def test_dashboard_kpi_labels_render(client):
    client.force_login(UserFactory())
    response = client.get("/")
    for label in (b"Lead totali", b"FTD", b"Conversione", b"Broker attivi"):
        assert label in response.content


@pytest.mark.django_db
def test_dashboard_welcome_uses_first_name(client):
    client.force_login(UserFactory(first_name="Alice"))
    response = client.get("/")
    assert b"Bentornato" in response.content
    assert b"Alice" in response.content


@pytest.mark.django_db
def test_dashboard_renders_lead_sections(client):
    client.force_login(UserFactory())
    response = client.get("/")
    assert b"Lead per broker" in response.content
    assert b"Lead recenti" in response.content


@pytest.mark.django_db
def test_dashboard_context_has_broker_and_recent_leads(client):
    client.force_login(UserFactory())
    response = client.get("/")
    ctx = response.context
    assert isinstance(ctx["by_broker"], list)
    assert "recent_leads" in ctx
    assert "leads_today" in ctx


@pytest.mark.django_db
def test_dashboard_recent_leads_limited_to_10(client):
    from apps.tracking.models import Lead
    client.force_login(UserFactory())
    for i in range(12):
        Lead.objects.create(firstname=f"L{i}", email=f"l{i}@t.it")
    response = client.get("/")
    assert len(response.context["recent_leads"]) == 10


# ── Revenue chart JSON endpoint (ancora usato dal showcase) ────────────
@pytest.mark.django_db
def test_revenue_chart_partial_returns_json_data(client):
    client.force_login(UserFactory())
    response = client.get("/charts/revenue/?range=7d")
    assert response.status_code == 200
    assert "application/json" in response["Content-Type"]
    data = response.json()
    assert "series" in data and "categories" in data


@pytest.mark.django_db
def test_revenue_chart_supports_multiple_ranges(client):
    client.force_login(UserFactory())
    for r in ["7d", "30d", "90d"]:
        response = client.get(f"/charts/revenue/?range={r}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["categories"]) > 0


@pytest.mark.django_db
def test_revenue_chart_returns_revenue_and_orders_series(client):
    client.force_login(UserFactory())
    response = client.get("/charts/revenue/?range=7d")
    data = response.json()
    names = [s["name"] for s in data["series"]]
    assert "Revenue" in names and "Orders" in names
    for s in data["series"]:
        assert len(s["data"]) == len(data["categories"])


@pytest.mark.django_db
def test_revenue_chart_requires_auth(client):
    response = client.get("/charts/revenue/?range=7d")
    assert response.status_code == 302
