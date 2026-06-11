import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings


@pytest.mark.django_db
def test_reset_demo_refuses_when_demo_mode_off():
    """Safety belt: never wipe data on a non-demo deploy."""
    with override_settings(DEMO_MODE=False):
        with pytest.raises(CommandError, match="DEMO_MODE is False"):
            call_command("reset_demo", "--no-input")


@pytest.mark.django_db
def test_reset_demo_runs_when_demo_mode_on(capsys):
    """End-to-end: should flush + migrate + seed without raising."""
    from django.contrib.auth import get_user_model

    from apps.accounts.tests.factories import UserFactory

    User = get_user_model()
    UserFactory(username="leftover")
    assert User.objects.filter(username="leftover").exists()

    with override_settings(DEMO_MODE=True):
        call_command("reset_demo", "--no-input")

    # The leftover user is gone and the seeded demo user is back.
    assert not User.objects.filter(username="leftover").exists()
    assert User.objects.filter(username="demo").exists()


@pytest.mark.django_db
def test_reset_demo_force_overrides_demo_mode_check():
    """--force lets you wipe even with DEMO_MODE off (escape hatch)."""
    with override_settings(DEMO_MODE=False):
        # Should not raise.
        call_command("reset_demo", "--no-input", "--force")
