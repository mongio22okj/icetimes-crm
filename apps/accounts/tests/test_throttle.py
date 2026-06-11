import pytest
from django.core.cache import cache
from django.urls import reverse


@pytest.fixture(autouse=True)
def _clear_cache():
    """Each test gets a fresh in-memory cache so counters don't bleed."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_login_get_is_not_throttled(client):
    """The form render itself should never 429 — only POST attempts count."""
    for _ in range(50):
        r = client.get(reverse("login"))
        assert r.status_code == 200


@pytest.mark.django_db
def test_login_post_throttled_by_ip_after_20(client):
    """The 21st POST from one IP returns 429 with a Retry-After header."""
    for i in range(20):
        r = client.post(reverse("login"),
                        {"username": f"nope{i}", "password": "wrong"})
        assert r.status_code != 429, f"throttled too early at attempt {i + 1}"
    r = client.post(reverse("login"),
                    {"username": "nope-final", "password": "wrong"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers


@pytest.mark.django_db
def test_login_post_throttled_by_username_after_10(client):
    """Per-user limit kicks in even when each attempt comes from a fresh IP-ish path."""
    for i in range(10):
        r = client.post(
            reverse("login"),
            {"username": "alice", "password": f"wrong-{i}"},
            REMOTE_ADDR=f"10.0.0.{i + 1}",  # rotate IPs to dodge the IP bucket
        )
        assert r.status_code != 429
    r = client.post(
        reverse("login"),
        {"username": "alice", "password": "still-wrong"},
        REMOTE_ADDR="10.0.0.99",
    )
    assert r.status_code == 429


@pytest.mark.django_db
def test_login_throttle_uses_xff_when_present(client):
    """X-Forwarded-For first hop wins, so visitor IPs behind a proxy throttle correctly."""
    # 20 attempts from XFF=1.1.1.1 (with REMOTE_ADDR fixed to nginx-style 127.0.0.1)
    for i in range(20):
        r = client.post(
            reverse("login"),
            {"username": f"nope{i}", "password": "wrong"},
            HTTP_X_FORWARDED_FOR="1.1.1.1",
        )
        assert r.status_code != 429
    r = client.post(
        reverse("login"),
        {"username": "nope-final", "password": "wrong"},
        HTTP_X_FORWARDED_FOR="1.1.1.1",
    )
    assert r.status_code == 429

    # A different XFF should NOT be throttled.
    r2 = client.post(
        reverse("login"),
        {"username": "fresh", "password": "wrong"},
        HTTP_X_FORWARDED_FOR="2.2.2.2",
    )
    assert r2.status_code != 429


@pytest.mark.django_db
def test_throttle_only_applies_to_login_path(client):
    """Other URLs aren't subject to login-throttle counters."""
    for _ in range(50):
        r = client.get("/accounts/password-reset/")
        assert r.status_code != 429
