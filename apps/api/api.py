"""Apex API — Django Ninja entry point. Mounts at /api/v1/."""
from ninja import NinjaAPI

from apps.api.auth import KeyAuth
from apps.api.routers import notifications, products, webhooks

api = NinjaAPI(
    title="Apex CRM API",
    version="1.0.0",
    description="REST API for leads, products and broker integrations.",
    auth=KeyAuth(),
)

api.add_router("/products/", products.router, tags=["Products"])
api.add_router("/notifications/", notifications.router, tags=["Notifications"])
api.add_router("/webhooks/", webhooks.router, tags=["Webhooks"])
