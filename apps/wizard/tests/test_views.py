import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.wizard.models import WizardSubmission

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return UserFactory(is_staff=True)


def _step1_payload():
    return {"name": "Aigars", "email": "demo@example.com"}


def _step2_payload():
    return {"company": "Acme", "role": "PM", "team_size": "2-10"}


def _step3_payload():
    return {"theme": "dark", "notifications_enabled": "on"}


def test_start_resets_session(client, user):
    client.force_login(user)
    session = client.session
    session["wizard"] = {"name": "old"}
    session.save()
    r = client.get(reverse("wizard:start"))
    assert r.status_code == 302
    assert client.session.get("wizard") is None


def test_step1_post_persists_in_session_and_advances(client, user):
    client.force_login(user)
    r = client.post(reverse("wizard:step1"), data=_step1_payload())
    assert r.status_code == 302
    assert r.url == reverse("wizard:step2")
    assert client.session["wizard"]["name"] == "Aigars"


def test_step2_redirects_to_step1_when_no_session(client, user):
    client.force_login(user)
    r = client.get(reverse("wizard:step2"))
    assert r.status_code == 302
    assert r.url == reverse("wizard:step1")


def test_step3_redirects_to_step2_when_no_team_size(client, user):
    client.force_login(user)
    client.post(reverse("wizard:step1"), data=_step1_payload())  # only step 1 filled
    r = client.get(reverse("wizard:step3"))
    assert r.status_code == 302
    assert r.url == reverse("wizard:step2")


def test_full_flow_creates_submission_and_clears_session(client, user):
    client.force_login(user)
    client.post(reverse("wizard:step1"), data=_step1_payload())
    client.post(reverse("wizard:step2"), data=_step2_payload())
    client.post(reverse("wizard:step3"), data=_step3_payload())
    r = client.post(reverse("wizard:review"))
    assert r.status_code == 302
    assert r.url == reverse("wizard:done")

    submission = WizardSubmission.objects.get()
    assert submission.name == "Aigars"
    assert submission.email == "demo@example.com"
    assert submission.company == "Acme"
    assert submission.theme == "dark"
    assert submission.notifications_enabled is True
    # Session cleared
    assert "wizard" not in client.session


def test_review_redirects_to_step3_when_incomplete(client, user):
    client.force_login(user)
    client.post(reverse("wizard:step1"), data=_step1_payload())
    client.post(reverse("wizard:step2"), data=_step2_payload())
    r = client.get(reverse("wizard:review"))
    assert r.status_code == 302
    assert r.url == reverse("wizard:step3")
