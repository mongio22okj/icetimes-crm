"""Customers endpoints — list / create / retrieve / update / delete."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from ninja import Router

from apps.api.pagination import paginate
from apps.api.schemas import (
    CustomerIn,
    CustomerOut,
    CustomerPage,
    CustomerPatch,
    Error,
)
from apps.customers.models import Customer

router = Router()


@router.get("/", response=CustomerPage, summary="List customers")
def list_customers(
    request,
    q: str = "",
    status: str = "",
    cursor: str = "",
    limit: int = 25,
):
    """Cursor-paginated list. Supports `?q=` (icontains across name/email/company)
    and `?status=active|inactive`."""
    qs = Customer.objects.all()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(company__icontains=q))
    if status:
        qs = qs.filter(status=status)
    return paginate(qs, cursor=cursor or None, limit=limit)


@router.post("/", response={201: CustomerOut, 400: Error}, summary="Create customer")
def create_customer(request, payload: CustomerIn):
    if Customer.all_objects.filter(email__iexact=payload.email).exists():
        return 400, {"detail": "A customer with that email already exists."}
    customer = Customer.objects.create(**payload.dict())
    return 201, customer


@router.get("/{customer_id}/", response={200: CustomerOut, 404: Error},
            summary="Retrieve customer")
def get_customer(request, customer_id: int):
    customer = get_object_or_404(Customer, pk=customer_id)
    return customer


@router.patch("/{customer_id}/", response={200: CustomerOut, 404: Error, 400: Error},
              summary="Update customer (partial)")
def update_customer(request, customer_id: int, payload: CustomerPatch):
    customer = get_object_or_404(Customer, pk=customer_id)
    fields = payload.dict(exclude_unset=True)
    if "email" in fields:
        new_email = fields["email"].strip().lower()
        if Customer.all_objects.filter(email__iexact=new_email).exclude(pk=customer.pk).exists():
            return 400, {"detail": "A customer with that email already exists."}
    for k, v in fields.items():
        setattr(customer, k, v)
    customer.save()
    return customer


@router.delete("/{customer_id}/", response={204: None, 404: Error},
               summary="Archive customer (soft delete)")
def delete_customer(request, customer_id: int):
    customer = get_object_or_404(Customer, pk=customer_id)
    customer.archive()
    return 204, None
