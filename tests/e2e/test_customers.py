import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_customer_list_and_detail(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/customers/")
    rows = page.locator("table tbody tr")
    assert rows.count() > 0
    rows.first.locator("a").first.click()
    page.wait_for_url(lambda url: "/customers/" in url and url.rstrip("/").split("/")[-1].isdigit())
    assert page.locator("text=Contact").is_visible()
    assert page.locator("text=Lifetime").is_visible()


def test_create_customer_flow(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/customers/new/")
    page.fill("input[name='name']", "Alice Chen")
    page.fill("input[name='email']", "alice.chen@example.com")
    page.fill("input[name='phone']", "+1 555 1234")
    page.fill("input[name='company']", "Acme Co")
    page.click("button:has-text('Create customer')")
    page.wait_for_url(lambda url: "/customers/" in url and "new" not in url and "edit" not in url)
    assert page.locator("text=Alice Chen").first.is_visible()
    assert page.locator("text=alice.chen@example.com").is_visible()


def test_archive_customer(page, server_url, django_user_model):
    from apps.customers.tests.factories import CustomerFactory
    c = CustomerFactory(name="Archivable Person", email="archivable@example.com")
    _login(page, server_url)
    page.goto(f"{server_url}/customers/{c.pk}/")
    page.click("button:has-text('Archive customer')")
    page.wait_for_url(f"{server_url}/customers/")
    assert not page.locator("text=Archivable Person").is_visible()
