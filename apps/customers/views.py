from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_SUCCESS, toast
from apps.core.tables import BulkAction, Column, Filter, TableConfig, TableView

from .forms import CustomerForm
from .models import Customer

CUSTOMERS_TABLE = TableConfig(
    key="customers",
    bulk_actions=(
        BulkAction(slug="mark_active", label="Mark active", icon="check"),
        BulkAction(slug="mark_inactive", label="Mark inactive", icon="x"),
        BulkAction(
            slug="archive", label="Archive",
            icon="trash", destructive=True,
            confirm_text="Archive {n} customers? They'll be hidden from the list but their orders are kept.",
        ),
    ),
    columns=(
        Column(
            key="name", label="Customer",
            sortable=True, searchable=True, pinned=True,
            template="customers/_table_cells.html#customer",
        ),
        Column(
            key="email", label="Email",
            searchable=True, priority=2,
        ),
        Column(
            key="company", label="Company",
            searchable=True,
            filter=Filter("text", placeholder="Filter company…"),
        ),
        Column(
            key="status", label="Status",
            filter=Filter("select", choices=Customer.STATUS),
            template="customers/_table_cells.html#status",
        ),
        Column(
            key="orders_count", label="Orders",
            align="right", sortable=True, priority=2,
        ),
        Column(
            key="created_at", label="Joined",
            sortable=True, filter=Filter("daterange"), priority=2,
            formatter=lambda v: v.strftime("%b %d, %Y") if v else "",
        ),
    ),
    default_sort="-created_at",
    page_size=25,
    sticky_first=True,
    caption="Manage your customer directory.",
)


class CustomerListView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, StaffRequiredMixin, TableView):
    model = Customer
    template_name = "customers/customer_list.html"
    context_object_name = "customers"
    breadcrumb_title = "Customers"
    table_config = CUSTOMERS_TABLE

    def get_queryset(self):
        return super().get_queryset().annotate(orders_count=Count("orders", distinct=True))

    def handle_bulk_action(self, action, ids, request):
        # Restrict to ids the user can actually see (mirrors the list filter).
        targets = Customer.objects.filter(pk__in=ids)
        n = targets.count()
        if action.slug == "mark_active":
            targets.update(status="active")
            toast(request, LEVEL_SUCCESS, f"Marked {n} customers as active.")
        elif action.slug == "mark_inactive":
            targets.update(status="inactive")
            toast(request, LEVEL_SUCCESS, f"Marked {n} customers as inactive.")
        elif action.slug == "archive":
            from django.utils import timezone
            targets.update(deleted_at=timezone.now())
            toast(request, LEVEL_SUCCESS, f"Archived {n} customers.")
        return redirect("customers:list")


class CustomerDetailView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin, DetailView):
    model = Customer
    template_name = "customers/customer_detail.html"
    context_object_name = "customer"
    breadcrumb_parent = "customers:list"

    def get_breadcrumb_title(self) -> str:
        return self.object.name

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recent_orders"] = (
            self.object.orders.select_related().order_by("-created_at")[:10]
        )
        return ctx


class CustomerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customers/customer_form.html"
    breadcrumb_title = "New customer"
    breadcrumb_parent = "customers:list"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Customer created.")
        return response

    def get_success_url(self):
        return reverse_lazy("customers:detail", kwargs={"pk": self.object.pk})


class CustomerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customers/customer_form.html"
    context_object_name = "customer"
    breadcrumb_parent = "customers:list"

    def get_breadcrumb_title(self) -> str:
        return f"Edit {self.object.name}"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Customer updated.")
        return response

    def get_success_url(self):
        return reverse_lazy("customers:detail", kwargs={"pk": self.object.pk})


class CustomerArchiveView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                          StaffRequiredMixin, View):
    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        customer.archive()
        messages.success(request, f"{customer.name} archived.")
        return redirect("customers:list")
