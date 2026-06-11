"""Products endpoints — list / create / retrieve / update / delete."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from ninja import Router

from apps.api.pagination import paginate
from apps.api.schemas import Error, ProductIn, ProductOut, ProductPage
from apps.products.models import Product

router = Router()


@router.get("/", response=ProductPage, summary="List products")
def list_products(
    request,
    q: str = "",
    status: str = "",
    category_id: int | None = None,
    cursor: str = "",
    limit: int = 25,
):
    qs = Product.objects.all()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if category_id:
        qs = qs.filter(category_id=category_id)
    return paginate(qs, cursor=cursor or None, limit=limit)


@router.post("/", response={201: ProductOut, 400: Error}, summary="Create product")
def create_product(request, payload: ProductIn):
    if Product.objects.filter(sku=payload.sku).exists():
        return 400, {"detail": "A product with that SKU already exists."}
    product = Product.objects.create(**payload.dict())
    return 201, product


@router.get("/{product_id}/", response={200: ProductOut, 404: Error},
            summary="Retrieve product")
def get_product(request, product_id: int):
    return get_object_or_404(Product, pk=product_id)


@router.delete("/{product_id}/", response={204: None, 404: Error},
               summary="Delete product")
def delete_product(request, product_id: int):
    product = get_object_or_404(Product, pk=product_id)
    product.delete()
    return 204, None
