"""Signal handlers that fan out into ActivityEvent rows.

Wires post_save on key models (Customer, Order, Invoice, Project,
ProjectTask) plus auth login/logout signals. Kept tight on purpose —
the activity log isn't an audit trail of *every* mutation, just the
things a human reading the timeline would care about.
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.activity.services import record

# ── Auth ──────────────────────────────────────────────────────────────

@receiver(user_logged_in)
def _on_login(sender, request, user, **kwargs):
    record(actor=user, category="auth", verb="signed in",
           label=user.get_full_name() or user.username,
           url=f"/people/{user.username}/")


@receiver(user_logged_out)
def _on_logout(sender, request, user, **kwargs):
    if user is None:
        return
    record(actor=user, category="auth", verb="signed out",
           label=user.get_full_name() or user.username)


# ── Customer ──────────────────────────────────────────────────────────

def _on_customer_save(sender, instance, created, **kwargs):
    if not created:
        return
    record(category="customer", verb="created",
           label=f"Customer {instance.name}",
           url=f"/customers/{instance.pk}/")


# ── Order ─────────────────────────────────────────────────────────────

def _on_order_save(sender, instance, created, **kwargs):
    if created:
        record(category="order", verb="placed",
               label=f"Order #{instance.pk}",
               url=f"/orders/{instance.pk}/")


# ── Invoice ───────────────────────────────────────────────────────────

def _on_invoice_save(sender, instance, created, **kwargs):
    if created:
        record(category="invoice", verb="drafted",
               label=f"Invoice {getattr(instance, 'number', instance.pk)}",
               url=f"/invoices/{instance.pk}/")


# ── Project ───────────────────────────────────────────────────────────

def _on_project_save(sender, instance, created, **kwargs):
    if created:
        record(actor=getattr(instance, "owner", None),
               category="project", verb="created",
               label=f"Project {instance.name}",
               url=f"/projects/{instance.slug}/")


# ── ProjectTask ───────────────────────────────────────────────────────

def _on_task_save(sender, instance, created, **kwargs):
    if created:
        return
    if instance.status == "done":
        record(actor=getattr(instance, "assignee", None),
               category="task", verb="completed",
               label=f"Task '{instance.title}'",
               url=f"/projects/{instance.project.slug}/tasks/")


# ── Wire receivers lazily so apps/activity doesn't need to import the
# concrete models at module load (avoids ordering issues during tests).

def _connect():
    from apps.customers.models import Customer
    from apps.invoices.models import Invoice
    from apps.orders.models import Order
    from apps.projects.models import Project, ProjectTask

    post_save.connect(_on_customer_save, sender=Customer,
                      dispatch_uid="activity.customer.save")
    post_save.connect(_on_order_save, sender=Order,
                      dispatch_uid="activity.order.save")
    post_save.connect(_on_invoice_save, sender=Invoice,
                      dispatch_uid="activity.invoice.save")
    post_save.connect(_on_project_save, sender=Project,
                      dispatch_uid="activity.project.save")
    post_save.connect(_on_task_save, sender=ProjectTask,
                      dispatch_uid="activity.task.save")


_connect()
