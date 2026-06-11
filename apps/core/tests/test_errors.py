import pytest
from django.template.loader import render_to_string
from django.test import override_settings


@override_settings(DEBUG=False)
@pytest.mark.django_db
def test_404_uses_custom_template(client):
    response = client.get("/this-route-does-not-exist/")
    assert response.status_code == 404
    assert b"Page not found" in response.content


def test_403_template_renders():
    html = render_to_string("errors/403.html")
    assert "403" in html
    assert "Forbidden" in html or "permission" in html.lower() or "access" in html.lower()


def test_500_template_renders():
    html = render_to_string("errors/500.html")
    assert "500" in html
    assert "error" in html.lower() or "something went wrong" in html.lower()


def test_404_template_has_back_link():
    html = render_to_string("errors/404.html")
    assert 'href="/"' in html or 'href="/accounts/login/"' in html or "Back to" in html
