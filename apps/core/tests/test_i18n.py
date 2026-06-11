"""Phase 9 i18n smoke tests."""
import pytest
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext, override

pytestmark = pytest.mark.django_db


def test_languages_setting_includes_en_and_es():
    codes = {code for code, _ in settings.LANGUAGES}
    assert "en" in codes
    assert "es" in codes


def test_locale_paths_set():
    assert any("locale" in str(p) for p in settings.LOCALE_PATHS)


def test_set_language_url_resolves(client):
    """Django ships set_language at /i18n/setlang/."""
    r = client.post(reverse("set_language"), data={"language": "es"})
    # 302 redirect (next falls back to "/"), and language cookie set
    assert r.status_code == 302
    assert r.cookies.get(settings.LANGUAGE_COOKIE_NAME).value == "es"


def test_spanish_translation_for_dashboard():
    with override("es"):
        assert gettext("Dashboard") == "Tablero"
        assert gettext("Sign in") == "Iniciar sesión"
        assert gettext("Sign out") == "Cerrar sesión"


def test_english_default_returns_source_strings():
    with override("en"):
        assert gettext("Dashboard") == "Dashboard"
        assert gettext("Sign in") == "Sign in"


def test_login_page_renders_in_spanish_when_locale_set(client):
    """Switch language via cookie then load login page — assert Spanish strings."""
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "es"
    r = client.get(reverse("login"))
    assert r.status_code == 200
    # "Iniciar sesión" should appear
    assert "Iniciar sesión".encode() in r.content
    # English version should NOT
    assert b"Welcome back. Enter your credentials." not in r.content
