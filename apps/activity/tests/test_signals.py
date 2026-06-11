"""Verify post_save signal handlers fan out into ActivityEvent rows."""
import pytest

from apps.accounts.tests.factories import UserFactory
from apps.activity.models import ActivityEvent
from apps.customers.tests.factories import CustomerFactory
from apps.invoices.tests.factories import InvoiceFactory
from apps.orders.tests.factories import OrderFactory
from apps.projects.tests.factories import ProjectFactory, ProjectTaskFactory

pytestmark = pytest.mark.django_db


def test_customer_create_emits_event():
    before = ActivityEvent.objects.filter(category="customer").count()
    c = CustomerFactory()
    after = ActivityEvent.objects.filter(category="customer").count()
    assert after == before + 1
    e = ActivityEvent.objects.filter(category="customer").latest("created_at")
    assert e.label.startswith("Customer ")
    assert c.name in e.label


def test_order_create_emits_event():
    before = ActivityEvent.objects.filter(category="order").count()
    OrderFactory()
    after = ActivityEvent.objects.filter(category="order").count()
    assert after == before + 1


def test_invoice_create_emits_event():
    before = ActivityEvent.objects.filter(category="invoice").count()
    InvoiceFactory()
    after = ActivityEvent.objects.filter(category="invoice").count()
    assert after == before + 1


def test_project_create_emits_event_with_owner():
    owner = UserFactory()
    before = ActivityEvent.objects.filter(category="project").count()
    p = ProjectFactory(owner=owner)
    after = ActivityEvent.objects.filter(category="project").count()
    assert after == before + 1
    e = ActivityEvent.objects.filter(category="project").latest("created_at")
    assert e.actor == owner
    assert p.name in e.label


def test_task_completed_emits_event():
    p = ProjectFactory()
    t = ProjectTaskFactory(project=p, status="todo")
    before = ActivityEvent.objects.filter(category="task", verb="completed").count()
    t.status = "done"
    t.save()
    after = ActivityEvent.objects.filter(category="task", verb="completed").count()
    assert after == before + 1


def test_task_create_does_not_emit_completed_event():
    p = ProjectFactory()
    before = ActivityEvent.objects.filter(category="task").count()
    ProjectTaskFactory(project=p, status="todo")
    after = ActivityEvent.objects.filter(category="task").count()
    # Task creation alone should not log a "completed" event
    assert after == before


def test_login_emits_auth_event(client):
    user = UserFactory(username="loginuser")
    user.set_password("Test!Demo#2026")
    user.save()
    user.email_verified_at = user.date_joined
    user.save(update_fields=["email_verified_at"])
    before = ActivityEvent.objects.filter(category="auth", verb="signed in").count()
    client.login(username="loginuser", password="Test!Demo#2026")
    after = ActivityEvent.objects.filter(category="auth", verb="signed in").count()
    assert after == before + 1
