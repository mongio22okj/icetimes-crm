"""Orders endpoints — list / retrieve / status patch / delete."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from ninja import Router

from apps.api.pagination import paginate
from apps.api.schemas import (
    Error,
    OrderItemOut,
    OrderOut,
    OrderPage,
    OrderStatusPatch,
)
from apps.orders.models import Order

router = Router()


def _serialize_order(order: Order) -> dict:
    return {
        "id": order.id,
        "number": order.number,
        "customer_id": order.customer_id,
        "status": order.status,
        "total": order.total,
        "items": [
            OrderItemOut(
                id=item.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in order.items.all()
        ],
        "created_at": order.created_at,
    }


@router.get("/", response=OrderPage, summary="List orders")
def list_orders(
    request,
    status: str = "",
    customer_id: int | None = None,
    cursor: str = "",
    limit: int = 25,
):
    qs = Order.objects.select_related("customer").prefetch_related("items")
    if status:
        qs = qs.filter(status=status)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    page = paginate(qs, cursor=cursor or None, limit=limit)
    page["items"] = [_serialize_order(o) for o in page["items"]]
    return page


@router.get("/{order_id}/", response={200: OrderOut, 404: Error},
            summary="Retrieve order")
def get_order(request, order_id: int):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), pk=order_id,
    )
    return _serialize_order(order)


@router.patch("/{order_id}/status/", response={200: OrderOut, 404: Error, 400: Error},
              summary="Update order status")
def update_status(request, order_id: int, payload: OrderStatusPatch):
    valid = {choice[0] for choice in Order.STATUS}
    if payload.status not in valid:
        return 400, {"detail": f"status must be one of {sorted(valid)}"}
    order = get_object_or_404(Order, pk=order_id)
    order.status = payload.status
    order.save(update_fields=["status", "updated_at"])
    order.refresh_from_db()
    return _serialize_order(order)


@router.delete("/{order_id}/", response={204: None, 404: Error},
               summary="Delete order")
def delete_order(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id)
    order.delete()
    return 204, None
