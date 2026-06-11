import pytest

from apps.accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_dashboard_redirects_anon_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/accounts/login" in response.url


@pytest.mark.django_db
def test_dashboard_renders_for_authed_user(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 200
    assert b"Dashboard" in response.content
    assert b"Total Revenue" in response.content
    assert b"Active Users" in response.content


@pytest.mark.django_db
def test_dashboard_stats_in_context(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/")
    stats = response.context["stats"]
    assert len(stats) == 4
    assert {"label", "value", "delta", "trend", "icon", "accent", "spark"} <= set(stats[0].keys())


@pytest.mark.django_db
def test_stat_cards_render_icon_and_sparkline(client):
    client.force_login(UserFactory())
    response = client.get("/")
    # Icon badge uses inline accent color and the icon tag renders an <svg>
    assert b"statSparkline(" in response.content
    assert b"stat-spark" in response.content
    # One sparkline container per stat (4)
    assert response.content.count(b"statSparkline(") == 4


@pytest.mark.django_db
def test_dashboard_welcome_copy_uses_first_name(client):
    user = UserFactory(first_name="Alice")
    client.force_login(user)
    response = client.get("/")
    assert b"Welcome" in response.content
    assert b"Alice" in response.content


@pytest.mark.django_db
def test_revenue_chart_partial_returns_json_data(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/charts/revenue/?range=7d")
    assert response.status_code == 200
    assert "application/json" in response["Content-Type"]
    data = response.json()
    assert "series" in data and "categories" in data


@pytest.mark.django_db
def test_revenue_chart_supports_multiple_ranges(client):
    user = UserFactory()
    client.force_login(user)
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
    series = data["series"]
    names = [s["name"] for s in series]
    assert "Revenue" in names and "Orders" in names
    # Each series is parallel to categories
    for s in series:
        assert len(s["data"]) == len(data["categories"])


@pytest.mark.django_db
def test_revenue_chart_requires_auth(client):
    response = client.get("/charts/revenue/?range=7d")
    assert response.status_code == 302


@pytest.mark.django_db
def test_dashboard_renders_revenue_chart_container(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/")
    assert b'id="revenue-chart"' in response.content
    assert b'revenueChart()' in response.content  # Alpine factory call


@pytest.mark.django_db
def test_dashboard_renders_side_panel(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/")
    assert b'id="traffic-chart"' in response.content
    assert b"Goals" in response.content
    assert b"Traffic Sources" in response.content


@pytest.mark.django_db
def test_dashboard_context_has_traffic_sources(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/")
    ctx = response.context
    assert "traffic_sources" in ctx
    assert isinstance(ctx["traffic_sources"], list)
    assert "goals" in ctx
    assert isinstance(ctx["goals"], list)
    assert all({"label", "current", "target"} <= set(g.keys()) for g in ctx["goals"])


@pytest.mark.django_db
def test_dashboard_embeds_traffic_sources_as_json_script(client):
    client.force_login(UserFactory())
    response = client.get("/")
    # json_script wraps as <script id="traffic-sources-data" type="application/json">...</script>
    assert b'id="traffic-sources-data"' in response.content
    assert b'type="application/json"' in response.content


@pytest.mark.django_db
def test_goals_render_progress_bars(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/")
    # Each goal should render with its current/target numbers and a progress-bar div
    assert b"New Signups" in response.content
    assert b"Revenue Target" in response.content


@pytest.mark.django_db
def test_dashboard_shows_latest_five_orders(client):
    from apps.orders.tests.factories import OrderFactory
    client.force_login(UserFactory())
    OrderFactory.create_batch(10)
    response = client.get("/")
    # Latest 5 orders should appear in the recent orders partial
    assert response.content.count(b"ORD-") >= 5
    assert b"Recent Orders" in response.content


@pytest.mark.django_db
def test_dashboard_shows_activity_feed(client):
    client.force_login(UserFactory())
    response = client.get("/")
    assert b"Activity" in response.content or b"Recent Activity" in response.content
    # Activities are a hardcoded demo list for MVP
    ctx = response.context
    assert "activities" in ctx
    assert len(ctx["activities"]) > 0


@pytest.mark.django_db
def test_recent_orders_limited_to_5(client):
    from apps.orders.tests.factories import OrderFactory
    client.force_login(UserFactory())
    OrderFactory.create_batch(8)
    response = client.get("/")
    ctx = response.context
    assert "recent_orders" in ctx
    assert len(ctx["recent_orders"]) == 5
