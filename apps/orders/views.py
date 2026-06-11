from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_SUCCESS, toast
from apps.core.tables import BulkAction, Column, Filter, TableConfig, TableView

from .forms import OrderForm, OrderItemFormSet
from .models import Order

ORDERS_TABLE = TableConfig(
    key="orders",
    bulk_actions=(
        BulkAction(slug="mark_paid", label="Mark paid", icon="check"),
        BulkAction(slug="mark_shipped", label="Mark shipped", icon="package"),
        BulkAction(
            slug="cancel", label="Cancel",
            icon="x", destructive=True,
            confirm_text="Cancel {n} orders? This is reversible.",
        ),
    ),
    columns=(
        Column("number", "Number", searchable=True, pinned=True,
               template="orders/_table_cells.html#number"),
        Column("customer.name", "Customer", searchable=True,
               template="orders/_table_cells.html#customer",
               filter=Filter("text", placeholder="Filter customer…")),
        Column("status", "Status",
               filter=Filter("select", choices=Order.STATUS),
               template="orders/_table_cells.html#status"),
        Column("total", "Total",
               sortable=False, align="right",
               formatter=lambda v: f"${v}" if v is not None else ""),
        Column("created_at", "Date",
               sortable=True, filter=Filter("daterange"), priority=2,
               formatter=lambda v: v.strftime("%b %d, %Y") if v else ""),
    ),
    default_sort="-created_at",
    page_size=25,
    sticky_first=True,
    caption="Track every sale and its fulfilment status.",
)


class OrderListView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, TableView):
    model = Order
    template_name = "orders/order_list.html"
    context_object_name = "orders"
    breadcrumb_title = "Orders"
    table_config = ORDERS_TABLE

    def get_queryset(self):
        return super().get_queryset().select_related("customer").prefetch_related("items")

    def handle_bulk_action(self, action, ids, request):
        targets = Order.objects.filter(pk__in=ids)
        n = targets.count()
        if action.slug == "mark_paid":
            targets.update(status="paid")
            toast(request, LEVEL_SUCCESS, f"Marked {n} orders as paid.")
        elif action.slug == "mark_shipped":
            targets.update(status="shipped")
            toast(request, LEVEL_SUCCESS, f"Marked {n} orders as shipped.")
        elif action.slug == "cancel":
            targets.update(status="cancelled")
            toast(request, LEVEL_SUCCESS, f"Cancelled {n} orders.")
        return redirect("orders:list")


class OrderDetailView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, DetailView):
    model = Order
    template_name = "orders/order_detail.html"
    context_object_name = "order"
    breadcrumb_parent = "orders:list"

    def get_queryset(self):
        return Order.objects.select_related("customer").prefetch_related("items__product")

    def get_breadcrumb_title(self):
        return self.object.number


class OrderCreateView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, CreateView):
    model = Order
    form_class = OrderForm
    template_name = "orders/order_form.html"
    success_url = reverse_lazy("orders:list")
    breadcrumb_title = "New order"
    breadcrumb_parent = "orders:list"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.method == "POST":
            ctx["items_formset"] = OrderItemFormSet(self.request.POST, instance=self.object)
        else:
            ctx["items_formset"] = OrderItemFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            formset = OrderItemFormSet(self.request.POST, instance=self.object)
            if formset.is_valid():
                formset.save()
                return redirect(self.success_url)
        # Formset invalid — re-render with errors
        return self.render_to_response(self.get_context_data(form=form))


class OrderUpdateView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, UpdateView):
    model = Order
    form_class = OrderForm
    template_name = "orders/order_form.html"
    success_url = reverse_lazy("orders:list")
    breadcrumb_parent = "orders:list"

    def get_breadcrumb_title(self):
        return f"Edit {self.object.number}"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.method == "POST":
            ctx["items_formset"] = OrderItemFormSet(self.request.POST, instance=self.object)
        else:
            ctx["items_formset"] = OrderItemFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            formset = OrderItemFormSet(self.request.POST, instance=self.object)
            if formset.is_valid():
                formset.save()
                return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form))


class GenerateInvoiceFromOrderView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                                    StaffRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        from apps.invoices.models import Invoice, InvoiceItem

        order = get_object_or_404(Order, pk=pk)
        with transaction.atomic():
            invoice = Invoice.objects.create(
                customer=order.customer,
                order=order,
                issue_date=timezone.now().date(),
                due_date=timezone.now().date() + timedelta(days=30),
            )
            for oi in order.items.all():
                InvoiceItem.objects.create(
                    invoice=invoice,
                    description=oi.product.name if oi.product else "Item",
                    quantity=oi.quantity,
                    unit_price=oi.unit_price,
                )
        messages.success(
            request,
            f"Invoice {invoice.number} generated from order {order.number}.",
        )
        return redirect(invoice.get_absolute_url())
