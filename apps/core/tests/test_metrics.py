"""Test the env-gated Prometheus /__metrics/ endpoint.

Both gated states matter:
  - METRICS_ENABLED off (default): /__metrics/ is 404 — no exposure, no perf cost
  - METRICS_ENABLED on: /__metrics/ returns Prometheus text-exposition format
"""
import pytest


@pytest.mark.django_db
def test_metrics_endpoint_404s_when_disabled(client):
    """Default state — METRICS_ENABLED is unset; the path mustn't exist."""
    r = client.get("/__metrics/")
    assert r.status_code == 404


@pytest.mark.django_db
def test_metrics_setting_default_is_falsy_in_dev():
    """In dev settings (and by default in prod), metrics is off."""
    from django.conf import settings
    # METRICS_ENABLED only exists when set in prod.py; dev never sets it.
    # So the only valid states are "missing" or False.
    assert getattr(settings, "METRICS_ENABLED", False) is False


def test_django_prometheus_module_is_importable():
    """Sanity: the optional dep installs cleanly via the `metrics` extra.

    Skipped if not installed (so `uv sync` without the extra still passes).
    """
    pytest.importorskip("django_prometheus")
    from django_prometheus import urls
    # The module must expose urlpatterns (django-prometheus's contract).
    assert hasattr(urls, "urlpatterns")
