import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")
    # Wait until apexShell has hydrated the root — Alpine has run init() by then,
    # so the keydown listener is attached and nav_items are loaded.
    page.wait_for_function(
        "() => { const el = document.querySelector('[x-data=\"apexShell()\"]');"
        " return el && el._x_dataStack && el._x_dataStack.length > 0; }",
        timeout=5000,
    )


def test_command_palette_opens_with_cmd_k(page, server_url):
    _login(page, server_url)
    # Focus must be somewhere real for Meta+K to route through window.
    page.locator("body").click()
    page.keyboard.press("Meta+k")
    page.wait_for_selector("input#palette-input", state="visible", timeout=3000)
    assert page.is_visible("input#palette-input")


def test_command_palette_filters_and_navigates(page, server_url):
    _login(page, server_url)
    page.locator("body").click()
    page.keyboard.press("Meta+k")
    page.wait_for_selector("input#palette-input", state="visible", timeout=3000)
    page.fill("#palette-input", "ord")
    # Enter activates the highlighted (first) match
    page.keyboard.press("Enter")
    page.wait_for_url(f"{server_url}/orders/", timeout=3000)


def test_nav_user_dropdown_signs_out(page, server_url):
    _login(page, server_url)
    page.click('button[aria-label^="User menu for"]')
    page.wait_for_selector(
        'button[type="submit"]:has-text("Sign out")', state="visible", timeout=2000
    )
    page.click('button[type="submit"]:has-text("Sign out")')
    page.wait_for_url(f"{server_url}/accounts/login/", timeout=3000)


def test_mobile_drawer_opens_with_hamburger(page, server_url):
    page.set_viewport_size({"width": 400, "height": 800})
    _login(page, server_url)
    page.click('button[aria-label="Open menu"]')
    sidebar = page.locator('aside[aria-label="Sidebar"]')
    # Wait for the 200ms transform transition to settle.
    page.wait_for_timeout(400)
    box = sidebar.bounding_box()
    assert box is not None and box["x"] >= 0, (
        f"Sidebar should be on-screen when drawer open, got x={box}"
    )
    # The close-X sits inside the sidebar; the header palette trigger occupies
    # the same viewport row on mobile. `force=True` bypasses Playwright's
    # hit-test so we exercise the handler directly (the sidebar is z-40 above
    # the header's z-20 at runtime; this pass tests the close semantics).
    page.click(
        'aside[aria-label="Sidebar"] button[aria-label="Close menu"]', force=True
    )
    page.wait_for_timeout(400)
    box2 = sidebar.bounding_box()
    assert box2 is None or box2["x"] < 0, (
        f"Sidebar should be off-screen after close, got x={box2}"
    )


def test_breadcrumbs_on_order_detail(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/orders/")
    # Wait for the orders table to render
    page.wait_for_selector("table tbody tr", timeout=3000)
    # Click the first order's detail link (typically in the number column)
    first_link = page.locator("table tbody tr a").first
    first_link.click()
    page.wait_for_selector('nav[aria-label="Breadcrumb"]', timeout=3000)
    crumbs_text = page.locator('nav[aria-label="Breadcrumb"]').inner_text()
    assert "Dashboard" in crumbs_text
    assert "Orders" in crumbs_text
    # Terminal crumb is the order number like ORD-00029
    assert "ORD-" in crumbs_text


def test_palette_excludes_staff_only_for_non_staff(page, server_url, django_user_model):
    from django.utils import timezone
    user = django_user_model.objects.create_user(
        username="nobody", password="nobody1234", is_staff=False
    )
    user.email_verified_at = timezone.now()
    user.save()
    _login(page, server_url, username="nobody", password="nobody1234")
    page.locator("body").click()
    page.keyboard.press("Meta+k")
    page.wait_for_selector("input#palette-input", state="visible")
    page.fill("#palette-input", "users")
    page.wait_for_timeout(100)
    matches = page.locator('div[role="dialog"] button:has-text("Users")').count()
    assert matches == 0, "palette leaked staff-only Users page to non-staff user"
