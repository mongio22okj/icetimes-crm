"""Pydantic schemas — input + output shapes for every API endpoint.

We keep schemas centralized here (rather than next to each endpoint)
so users browsing the OpenAPI spec see consistent types across the
whole surface.

Naming convention:
  <Model>Out  — full read schema (response shape)
  <Model>In   — create schema (POST body)
  <Model>Patch — partial update schema (PATCH body, all fields optional)
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from ninja import Field, Schema

# ── Generic ────────────────────────────────────────────────────────────


class Page(Schema):
    """Cursor-style pagination wrapper used by every list endpoint."""
    items: list = Field(default_factory=list)
    next_cursor: str | None = None
    total: int


class Error(Schema):
    detail: str


# ── Customer ───────────────────────────────────────────────────────────


class CustomerOut(Schema):
    id: int
    name: str
    email: str
    phone: str = ""
    company: str = ""
    status: str
    address: str = ""
    city: str = ""
    country: str = ""
    notes: str = ""
    created_at: datetime
    updated_at: datetime


class CustomerIn(Schema):
    name: str
    email: str
    phone: str = ""
    company: str = ""
    status: str = "active"
    address: str = ""
    city: str = ""
    country: str = ""
    notes: str = ""


class CustomerPatch(Schema):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    status: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    notes: str | None = None


class CustomerPage(Schema):
    items: list[CustomerOut]
    next_cursor: str | None = None
    total: int


# ── Product ────────────────────────────────────────────────────────────


class ProductOut(Schema):
    id: int
    name: str
    sku: str
    price: Decimal
    stock: int
    status: str
    category_id: int | None = None
    description: str = ""
    created_at: datetime


class ProductIn(Schema):
    name: str
    sku: str
    price: Decimal
    stock: int = 0
    status: str = "draft"
    category_id: int | None = None
    description: str = ""


class ProductPage(Schema):
    items: list[ProductOut]
    next_cursor: str | None = None
    total: int


# ── Order ──────────────────────────────────────────────────────────────


class OrderItemOut(Schema):
    id: int
    product_id: int | None = None
    quantity: int
    unit_price: Decimal


class OrderOut(Schema):
    id: int
    number: str
    customer_id: int
    status: str
    total: Decimal
    items: list[OrderItemOut]
    created_at: datetime


class OrderPage(Schema):
    items: list[OrderOut]
    next_cursor: str | None = None
    total: int


class OrderStatusPatch(Schema):
    """Lightweight PATCH for status transitions only — full edit goes
    through the dashboard form (it has line-item formsets)."""
    status: str


# ── Invoice ────────────────────────────────────────────────────────────


class InvoiceItemOut(Schema):
    id: int
    description: str
    quantity: int
    unit_price: Decimal


class InvoiceOut(Schema):
    id: int
    number: str
    customer_id: int
    order_id: int | None = None
    status: str
    issue_date: date
    due_date: date
    total: Decimal
    items: list[InvoiceItemOut]


class InvoicePage(Schema):
    items: list[InvoiceOut]
    next_cursor: str | None = None
    total: int


# ── Notification ───────────────────────────────────────────────────────


class NotificationOut(Schema):
    id: int
    category: str
    kind: str
    title: str
    body: str = ""
    url: str = ""
    actor_id: int | None = None
    read_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime


class NotificationPage(Schema):
    items: list[NotificationOut]
    next_cursor: str | None = None
    total: int


# ── Webhook ────────────────────────────────────────────────────────────


class WebhookOut(Schema):
    id: int
    name: str = ""
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime


class WebhookIn(Schema):
    name: str = ""
    url: str
    events: list[str]
    is_active: bool = True


class WebhookCreated(WebhookOut):
    """Returned from POST — includes `secret` exactly once."""
    secret: str


class WebhookPage(Schema):
    items: list[WebhookOut]
    next_cursor: str | None = None
    total: int
