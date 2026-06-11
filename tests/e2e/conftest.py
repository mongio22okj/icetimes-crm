import os

import pytest
from django.core.management import call_command

# pytest-playwright starts sync_playwright() in session scope, which runs an event loop.
# Django 5.1+ raises SynchronousOnlyOperation when it detects a running event loop.
# This flag disables that guard — safe for tests since we're not doing async Django.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture(autouse=True)
def seed_demo_data(transactional_db):
    """Seed demo data before each E2E test.

    Uses transactional_db (required by live_server) — each test gets a fresh DB,
    so seed_demo must run per-test rather than once per session.
    """
    call_command("seed_demo", verbosity=0)


@pytest.fixture
def server_url(live_server):
    """Return the URL of the test Django server."""
    return live_server.url
