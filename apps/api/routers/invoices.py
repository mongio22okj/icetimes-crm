"""Invoices endpoints — list / retrieve + transition actions."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from ninja import Router

from apps.api.pagination import paginate
from apps.api.schemas import (
    Error,
    InvoiceItemOut,
    InvoiceOut,
    InvoicePage,
)
from apps.invoices.models import InvalidTransition, Invoice

router = Router()


def _serialize_invoice(invoice: Invoice) -> dict:
    return {
        "id": invoice.id,
        "number": invoice.number,
        "customer_id": invoice.customer_id,
        "order_id": invoice.order_id,
        "status": invoice.status,
        "issue_date": invoice.issue_date,
        "due_date": invoice.due_date,
        "total": invoice.total,
        "items": [
            InvoiceItemOut(
                id=item.id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in invoice.items.all()
        ],
    }


@router.get("/", response=InvoicePage, summary="List invoices")
def list_invoices(
    request,
    status: str = "",
    customer_id: int | None = None,
    cursor: str = "",
    limit: int = 25,
):
    qs = Invoice.objects.select_related("customer").prefetch_related("items")
    if status:
        qs = qs.filter(status=status)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    page = paginate(qs, cursor=cursor or None, limit=limit)
    page["items"] = [_serialize_invoice(i) for i in page["items"]]
    return page


@router.get("/{invoice_id}/", response={200: InvoiceOut, 404: Error},
            summary="Retrieve invoice")
def get_invoice(request, invoice_id: int):
    inv = get_object_or_404(
        Invoice.objects.prefetch_related("items"), pk=invoice_id,
    )
    return _serialize_invoice(inv)


@router.post("/{invoice_id}/send/", response={200: InvoiceOut, 400: Error, 404: Error},
             summary="Mark invoice as sent")
def send_invoice(request, invoice_id: int):
    inv = get_object_or_404(Invoice, pk=invoice_id)
    try:
        inv.transition_to("sent")
    except InvalidTransition as e:
        return 400, {"detail": str(e)}
    inv.refresh_from_db()
    return _serialize_invoice(inv)


@router.post("/{invoice_id}/pay/", response={200: InvoiceOut, 400: Error, 404: Error},
             summary="Mark invoice as paid")
def pay_invoice(request, invoice_id: int):
    inv = get_object_or_404(Invoice, pk=invoice_id)
    try:
        inv.transition_to("paid")
    except InvalidTransition as e:
        return 400, {"detail": str(e)}
    inv.refresh_from_db()
    return _serialize_invoice(inv)


@router.post("/{invoice_id}/void/", response={200: InvoiceOut, 400: Error, 404: Error},
             summary="Void invoice")
def void_invoice(request, invoice_id: int):
    inv = get_object_or_404(Invoice, pk=invoice_id)
    try:
        inv.transition_to("void")
    except InvalidTransition as e:
        return 400, {"detail": str(e)}
    inv.refresh_from_db()
    return _serialize_invoice(inv)
