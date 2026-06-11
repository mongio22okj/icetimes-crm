import json
from unittest.mock import patch

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_returns_200_when_all_checks_pass(client):
    r = client.get(reverse("health"))
    assert r.status_code == 200
    body = json.loads(r.content)
    assert body["status"] == "ok"
    assert body["checks"]["db"]["ok"] is True
    # In-memory channel layer answers ping fine.
    assert body["checks"]["channel_layer"]["ok"] is True
    assert body["failed"] == []


@pytest.mark.django_db
def test_health_returns_503_when_db_check_fails(client):
    with patch("apps.core.health._check_db", return_value={"ok": False, "error": "boom"}):
        r = client.get(reverse("health"))
    assert r.status_code == 503
    body = json.loads(r.content)
    assert body["status"] == "degraded"
    assert "db" in body["failed"]


@pytest.mark.django_db
def test_health_response_is_no_cache(client):
    r = client.get(reverse("health"))
    assert "no-store" in r.headers.get("Cache-Control", "")


@pytest.mark.django_db
def test_health_only_accepts_get(client):
    r = client.post(reverse("health"))
    assert r.status_code == 405
