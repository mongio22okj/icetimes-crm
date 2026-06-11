"""Invoice CRUD + HTMX row-add. Transitions (send/pay/void) added in Task 4,
PDF view in Task 5, public views in Task 6."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models, transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_SUCCESS, toast
from apps.core.tables import BulkAction, Column, Filter, TableConfig, TableView
from apps.invoices.forms import InvoiceForm, InvoiceItemFormSet
from apps.invoices.models import InvalidTransition, Invoice

INVOICES_TABLE = TableConfig(
    key="invoices",
    bulk_actions=(
        BulkAction(slug="mark_sent", label="Mark sent", icon="mail"),
        BulkAction(slug="mark_paid", label="Mark paid", icon="check"),
        BulkAction(
            slug="void", label="Void",
            icon="x", destructive=True,
            confirm_text="Void {n} invoices? This cannot be reversed.",
        ),
    ),
    columns=(
        Column("number", "Number", searchable=True, pinned=True,
               template="invoices/_table_cells.html#number"),
        Column("customer.name", "Customer", searchable=True,
               filter=Filter("text", placeholder="Filter customer…")),
        Column("issue_date", "Issue", sortable=True,
               filter=Filter("daterange"), priority=2,
               formatter=lambda v: v.strftime("%b %-d, %Y") if v else ""),
        Column("due_date", "Due", sortable=True,
               filter=Filter("daterange"), priority=2,
               formatter=lambda v: v.strftime("%b %-d, %Y") if v else ""),
        Column("status", "Status",
               filter=Filter("select", choices=Invoice.STATUS_CHOICES),
               template="invoices/_table_cells.html#status"),
        Column("total", "Total",
               sortable=False, align="right",
               formatter=lambda v: f"${v:.2f}" if v is not None else ""),
    ),
    default_sort="-issue_date",
    page_size=25,
    sticky_first=True,
    caption="Track billing, lifecycle status, and totals.",
)


class InvoiceListView(BreadcrumbsMixin, LoginRequiredMixin,
                      EmailVerifiedRequiredMixin, StaffRequiredMixin, TableView):
    model = Invoice
    template_name = "invoices/invoice_list.html"
    context_object_name = "invoices"
    breadcrumb_title = "Invoices"
    table_config = INVOICES_TABLE

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("customer")
            .annotate(items_count=models.Count("items", distinct=True))
        )

    def handle_bulk_action(self, action, ids, request):
        targets = Invoice.objects.filter(pk__in=ids)
        n = targets.count()
        if action.slug == "mark_sent":
            targets.filter(status="draft").update(status="sent")
            toast(request, LEVEL_SUCCESS, f"Marked {n} invoices as sent.")
        elif action.slug == "mark_paid":
            targets.filter(status__in=("draft", "sent")).update(status="paid")
            toast(request, LEVEL_SUCCESS, f"Marked {n} invoices as paid.")
        elif action.slug == "void":
            targets.exclude(status="paid").update(status="void")
            toast(request, LEVEL_SUCCESS, f"Voided {n} invoices.")
        return redirect("invoices:list")


class InvoiceDetailView(BreadcrumbsMixin, LoginRequiredMixin,
                        EmailVerifiedRequiredMixin, StaffRequiredMixin, DetailView):
    model = Invoice
    template_name = "invoices/invoice_detail.html"
    context_object_name = "invoice"
    breadcrumb_parent = "invoices:list"

    def get_breadcrumb_title(self) -> str:
        return self.object.number

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all()
        return ctx


class _InvoiceFormMixin:
    """Shared form_valid that saves the header + formset transactionally."""

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]
        if not formset.is_valid():
            return self.form_invalid(form)
        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        messages.success(self.request, f"Invoice {self.object.number} saved.")
        return redirect(self.object.get_absolute_url())


class InvoiceCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                        EmailVerifiedRequiredMixin, StaffRequiredMixin,
                        _InvoiceFormMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "invoices/invoice_form.html"
    breadcrumb_title = "New invoice"
    breadcrumb_parent = "invoices:list"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx["formset"] = InvoiceItemFormSet(self.request.POST, prefix="items")
        else:
            ctx["formset"] = InvoiceItemFormSet(prefix="items")
        return ctx


class InvoiceUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                        EmailVerifiedRequiredMixin, StaffRequiredMixin,
                        _InvoiceFormMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "invoices/invoice_form.html"
    context_object_name = "invoice"
    breadcrumb_parent = "invoices:list"

    def get_breadcrumb_title(self) -> str:
        return f"Edit {self.object.number}"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status != "draft":
            return HttpResponseForbidden("Only draft invoices can be edited.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx["formset"] = InvoiceItemFormSet(
                self.request.POST, instance=self.object, prefix="items"
            )
        else:
            ctx["formset"] = InvoiceItemFormSet(instance=self.object, prefix="items")
        return ctx


class InvoiceDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                        StaffRequiredMixin, View):
    """POST-only. Only drafts can be deleted."""

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        if invoice.status != "draft":
            return HttpResponseForbidden("Only draft invoices can be deleted.")
        number = invoice.number
        invoice.delete()
        messages.success(request, f"Draft invoice {number} deleted.")
        return redirect("invoices:list")


class InvoiceItemAddRowView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             StaffRequiredMixin, View):
    """HTMX helper: return a blank item row <tr> with the given form index."""

    def get(self, request):
        try:
            index = int(request.GET.get("index", 0))
        except (TypeError, ValueError):
            index = 0
        formset = InvoiceItemFormSet(prefix="items")
        empty_form = formset.empty_form
        empty_form.prefix = f"items-{index}"
        return render(request, "invoices/_invoice_item_row.html", {"form": empty_form})


class _TransitionView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                      StaffRequiredMixin, View):
    """POST-only status transition endpoint."""

    http_method_names = ["post"]
    action = ""  # one of sent / paid / void
    success_msg = ""

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        method = getattr(invoice, f"mark_{self.action}")
        try:
            method()
        except InvalidTransition as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, self.success_msg.format(number=invoice.number))
        return redirect(invoice.get_absolute_url())


class InvoiceSendView(_TransitionView):
    action = "sent"
    success_msg = "Invoice {number} marked as sent."


class InvoicePayView(_TransitionView):
    action = "paid"
    success_msg = "Invoice {number} marked as paid."


class InvoiceVoidView(_TransitionView):
    action = "void"
    success_msg = "Invoice {number} voided."


class InvoicePdfView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                     StaffRequiredMixin, View):
    def get(self, request, pk):
        from apps.invoices.pdf import render_invoice_pdf
        invoice = get_object_or_404(Invoice, pk=pk)
        pdf = render_invoice_pdf(invoice, request=request)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{invoice.number}.pdf"'
        )
        return response


class PublicInvoiceView(DetailView):
    """Anonymous token-gated read-only invoice view. Drafts 404."""

    model = Invoice
    slug_field = "public_token"
    slug_url_kwarg = "token"
    template_name = "invoices/invoice_public.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return Invoice.objects.public_visible().select_related("customer")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all()
        return ctx


class PublicInvoicePdfView(View):
    def get(self, request, token):
        from apps.invoices.pdf import render_invoice_pdf
        invoice = get_object_or_404(
            Invoice.objects.public_visible(), public_token=token
        )
        pdf = render_invoice_pdf(invoice, request=request)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{invoice.number}.pdf"'
        )
        return response
