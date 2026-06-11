"""Test the custom CSRF_FAILURE_VIEW."""
import pytest
from django.conf import settings
from django.test import Client


@pytest.mark.django_db
def test_csrf_failure_view_setting_points_to_our_view():
    assert settings.CSRF_FAILURE_VIEW == "apps.core.views.csrf_failure"


@pytest.mark.django_db
def test_csrf_failure_view_renders_friendly_page():
    """A POST without the CSRF token must render our custom page,
    not Django's bare-bones default."""
    # enforce_csrf_checks=True forces the middleware to run even without
    # a CsrfViewMiddleware bypass.
    client = Client(enforce_csrf_checks=True)
    r = client.post("/accounts/login/",
                    {"username": "demo", "password": "wrong"})
    assert r.status_code == 403
    body = r.content.decode()
    # Friendly copy from our template
    assert "Session expired" in body
    assert "Refresh and retry" in body
    # The bare Django template starts "Forbidden (403)" — should NOT be present
    assert "CSRF verification failed. Request aborted." not in body


@pytest.mark.django_db
def test_csrf_failure_view_returns_403_status():
    client = Client(enforce_csrf_checks=True)
    r = client.post("/accounts/login/", {"username": "x", "password": "y"})
    assert r.status_code == 403
