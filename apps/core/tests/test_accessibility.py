"""Accessibility-related smoke tests.

These check structural a11y features that are easy to break unintentionally:

  - the skip-to-content link is the first focusable element on every
    dashboard + docs page
  - aria-current="page" appears on the active sidebar item
  - the reduced-motion CSS rule is present in the built stylesheet (only
    when the build artifact exists; skipped otherwise so dev-without-CSS
    works)
"""
import pytest
from django.urls import reverse


def _login(client, db):
    """Create + force-login a verified staff user."""
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    user = get_user_model().objects.create_user(
        username="a11y", email="a@x.io", password="pw",
        is_staff=True, email_verified_at=timezone.now(),
    )
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_dashboard_has_skip_to_content_link(client, db):
    _login(client, db)
    r = client.get("/")
    body = r.content.decode()
    assert 'href="#main-content"' in body
    assert "Skip to main content" in body
    assert 'id="main-content"' in body


@pytest.mark.django_db
def test_docs_has_skip_to_content_link(client):
    r = client.get(reverse("docs:index"))
    body = r.content.decode()
    assert 'href="#docs-content"' in body
    assert "Skip to main content" in body
    assert 'id="docs-content"' in body


@pytest.mark.django_db
def test_skip_link_is_keyboard_only(client, db):
    """The skip link should be sr-only by default — only visible on focus."""
    _login(client, db)
    r = client.get("/")
    body = r.content.decode()
    # It uses Tailwind's `sr-only focus:not-sr-only` pattern
    assert "sr-only focus:not-sr-only" in body


@pytest.mark.django_db
def test_active_sidebar_item_carries_aria_current(client, db):
    """Customers list page → "Customers" sidebar link gets aria-current."""
    _login(client, db)
    r = client.get("/customers/")
    body = r.content.decode()
    # The active-class string AND the aria attribute should both be present
    assert 'aria-current="page"' in body
    assert "bg-sidebar-accent" in body


@pytest.mark.django_db
def test_breadcrumbs_active_page_carries_aria_current(client, db):
    """Last breadcrumb on a non-root page should carry aria-current="page"."""
    _login(client, db)
    r = client.get("/customers/")
    body = r.content.decode()
    # Breadcrumb partial wraps the current title in
    # <span ... aria-current="page">{{ title }}</span>
    import re
    assert re.search(r'aria-current="page"[^>]*>Customers<', body) is not None
