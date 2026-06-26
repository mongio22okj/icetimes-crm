"""Self-serve billing surface — current plan, payment methods, plan
comparison, cancel/reactivate flow.

This is a Stripe-Customer-Portal-style replacement template, kept
intentionally provider-agnostic. Real integrations should keep the model
shapes and replace the form-submit handlers with provider API calls.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from apps.accounts.mixins import EmailVerifiedRequiredMixin

from .forms import PaymentMethodForm
from .models import PaymentMethod, Subscription


def _get_or_create_subscription(user) -> Subscription:
    """Lazily ensure each user has a Subscription row.

    Real integration would create this on signup or via webhook; here we
    create on first /billing/ visit so the showcase always has data.
    """
    sub, created = Subscription.objects.get_or_create(
        user=user,
        defaults={
            "plan": "starter",
            "status": "active",
            "billing_cycle": "monthly",
            "amount": Decimal("19"),
            "billing_email": user.email,
            "renews_at": timezone.now() + timedelta(days=18),
            "usage_seats": 3,
            "usage_storage_gb": 4,
            "usage_api_calls": 7240,
        },
    )
    return sub


@login_required
def overview(request):
    sub = _get_or_create_subscription(request.user)
    payment_methods = sub.payment_methods.all()
    # Recent invoices: reuse the existing invoices app to surface 5 latest
    # for the current user as a stand-in for billing history.
    try:
        from apps.invoices.models import Invoice
        recent_invoices = Invoice.objects.order_by("-created_at")[:5]
    except Exception:  # noqa: BLE001
        recent_invoices = []
    return render(request, "billing/overview.html", {
        "subscription": sub,
        "payment_methods": payment_methods,
        "default_pm": payment_methods.filter(is_default=True).first(),
        "recent_invoices": recent_invoices,
        "limits": sub.limits,
        "breadcrumbs": [("Settings", "/settings/profile/"), ("Billing", None)],
    })


@login_required
def plans(request):
    sub = _get_or_create_subscription(request.user)
    cycle = request.GET.get("cycle", sub.billing_cycle or "monthly")
    if cycle not in ("monthly", "annual"):
        cycle = "monthly"

    tiers = []
    for plan_key, _label in Subscription.PLAN_CHOICES:
        monthly, annual = Subscription.PLAN_PRICING[plan_key]
        price = monthly if cycle == "monthly" else annual
        tiers.append({
            "key": plan_key,
            "name": dict(Subscription.PLAN_CHOICES)[plan_key],
            "price": price,
            "monthly": monthly,
            "annual": annual,
            "cycle": cycle,
            "limits": Subscription.PLAN_LIMITS[plan_key],
            "is_current": sub.plan == plan_key,
            "highlight": plan_key == "pro",
        })
    return render(request, "billing/plans.html", {
        "subscription": sub,
        "tiers": tiers,
        "cycle": cycle,
        "breadcrumbs": [("Settings", "/settings/profile/"), ("Billing", "/billing/"), ("Plans", None)],
    })


class ChangePlanView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def post(self, request):
        sub = _get_or_create_subscription(request.user)
        plan = request.POST.get("plan", "")
        cycle = request.POST.get("cycle", sub.billing_cycle)
        if plan not in dict(Subscription.PLAN_CHOICES):
            raise Http404("Unknown plan")
        if cycle not in ("monthly", "annual"):
            cycle = "monthly"
        monthly, annual = Subscription.PLAN_PRICING[plan]
        sub.plan = plan
        sub.billing_cycle = cycle
        sub.amount = monthly if cycle == "monthly" else annual
        sub.status = "active"
        sub.canceled_at = None
        sub.save()
        messages.success(request,
            f"Plan changed to {sub.get_plan_display()} ({sub.get_billing_cycle_display().lower()}).")
        return redirect("billing:overview")


class PaymentMethodsView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def get(self, request):
        sub = _get_or_create_subscription(request.user)
        return render(request, "billing/payment_methods.html", {
            "subscription": sub,
            "payment_methods": sub.payment_methods.all(),
            "form": PaymentMethodForm(),
            "breadcrumbs": [("Settings", "/settings/profile/"),
                            ("Billing", "/billing/"), ("Payment methods", None)],
        })

    def post(self, request):
        sub = _get_or_create_subscription(request.user)
        form = PaymentMethodForm(request.POST)
        if form.is_valid():
            pm = form.save(commit=False)
            pm.subscription = sub
            # First card auto-default
            if not sub.payment_methods.exists():
                pm.is_default = True
            pm.save()
            messages.success(request, f"Added {pm}.")
            return redirect("billing:payment_methods")
        return render(request, "billing/payment_methods.html", {
            "subscription": sub,
            "payment_methods": sub.payment_methods.all(),
            "form": form,
            "breadcrumbs": [("Settings", "/settings/profile/"),
                            ("Billing", "/billing/"), ("Payment methods", None)],
        })


class SetDefaultPaymentMethodView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def post(self, request, pk):
        sub = _get_or_create_subscription(request.user)
        pm = get_object_or_404(PaymentMethod, pk=pk, subscription=sub)
        pm.is_default = True
        pm.save()
        messages.success(request, f"{pm} is now your default.")
        return redirect("billing:payment_methods")


class DeletePaymentMethodView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def post(self, request, pk):
        sub = _get_or_create_subscription(request.user)
        pm = get_object_or_404(PaymentMethod, pk=pk, subscription=sub)
        pm.delete()
        messages.success(request, "Card removed.")
        return redirect("billing:payment_methods")


class CancelView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def get(self, request):
        sub = _get_or_create_subscription(request.user)
        return render(request, "billing/cancel.html", {
            "subscription": sub,
            "breadcrumbs": [("Settings", "/settings/profile/"),
                            ("Billing", "/billing/"), ("Cancel", None)],
        })

    def post(self, request):
        sub = _get_or_create_subscription(request.user)
        if sub.is_canceled:
            sub.reactivate()
            messages.success(request, "Subscription reactivated.")
        else:
            sub.cancel()
            messages.success(request, "Subscription canceled. You'll keep access until period end.")
        return redirect(reverse("billing:overview"))
