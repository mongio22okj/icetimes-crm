"""Apex API — Django Ninja entry point.

Mounts at `/api/v1/`. OpenAPI schema is auto-derived; Swagger UI lives
at `/api/docs/` (default Ninja path).

Endpoints are split into routers per domain (customers / products /
orders / invoices / notifications / webhooks). All endpoints require
KeyAuth — `Authorization: Bearer apex_<token>` — except the OpenAPI
schema/docs themselves.
"""
from ninja import NinjaAPI

from apps.api.auth import KeyAuth
from apps.api.routers import customers, invoices, notifications, orders, products, webhooks

api = NinjaAPI(
    title="Apex API",
    version="1.0.0",
    description=(
        "REST API over the core Apex domain models. Authenticate with a "
        "bearer token issued at /settings/api-tokens/. All endpoints "
        "use cursor pagination via `?cursor=<id>&limit=<N>` (max 100)."
    ),
    auth=KeyAuth(),
)

api.add_router("/customers/", customers.router, tags=["Customers"])
api.add_router("/products/", products.router, tags=["Products"])
api.add_router("/orders/", orders.router, tags=["Orders"])
api.add_router("/invoices/", invoices.router, tags=["Invoices"])
api.add_router("/notifications/", notifications.router, tags=["Notifications"])
api.add_router("/webhooks/", webhooks.router, tags=["Webhooks"])
