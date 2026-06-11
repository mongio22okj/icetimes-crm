"""Webhook dispatch + signing tests."""
import json
from unittest.mock import patch

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.api.dispatch import dispatch_webhook
from apps.api.models import Webhook, WebhookDelivery, serialize_event_payload

pytestmark = pytest.mark.django_db


def test_dispatch_skips_when_no_subscribers():
    """No matching subscribers → nothing recorded, no errors."""
    n = dispatch_webhook("invoice.paid", {"id": 1})
    assert n == 0
    assert WebhookDelivery.objects.count() == 0


def test_dispatch_only_fires_matching_event():
    user = UserFactory()
    Webhook.objects.create(user=user, url="https://x.example",
                           events="invoice.paid", secret="s", is_active=True)
    Webhook.objects.create(user=user, url="https://y.example",
                           events="customer.created", secret="s", is_active=True)
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.status = 200
        mock_open.return_value.__enter__.return_value.read.return_value = b""
        n = dispatch_webhook("invoice.paid", {"id": 1})
    assert n == 1
    # Only the matching webhook got a delivery row.
    assert WebhookDelivery.objects.count() == 1


def test_dispatch_skips_inactive_subscribers():
    user = UserFactory()
    Webhook.objects.create(user=user, url="https://x.example",
                           events="invoice.paid", secret="s", is_active=False)
    n = dispatch_webhook("invoice.paid", {"id": 1})
    assert n == 0


def test_dispatch_records_failed_delivery_on_network_error():
    user = UserFactory()
    Webhook.objects.create(user=user, url="https://will-fail.example",
                           events="x.y", secret="s", is_active=True)
    with patch("urllib.request.urlopen", side_effect=Exception("boom")):
        dispatch_webhook("x.y", {"a": 1})
    delivery = WebhookDelivery.objects.get()
    assert delivery.status == "failed"
    assert "boom" in delivery.response_body


def test_dispatch_signs_payload_with_hmac_sha256():
    user = UserFactory()
    w = Webhook.objects.create(user=user, url="https://x.example",
                               events="t.t", secret="topsecret", is_active=True)
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["headers"] = dict(req.header_items())
        captured["body"] = req.data
        from contextlib import contextmanager

        class _R:
            status = 200
            def read(self, *a, **kw):
                return b""

        @contextmanager
        def cm():
            yield _R()
        return cm()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        dispatch_webhook("t.t", {"a": 1})

    sig = captured["headers"].get("X-apex-signature") or captured["headers"].get("X-Apex-Signature")
    assert sig is not None and sig.startswith("sha256=")
    # Verify locally
    expected = w.sign(captured["body"])
    assert sig == f"sha256={expected}"


def test_serialize_event_payload_is_deterministic():
    """JSON encoding must be sort-keys + no whitespace so signatures
    reproduce across Python versions."""
    a = serialize_event_payload("e", {"b": 2, "a": 1})
    b = serialize_event_payload("e", {"a": 1, "b": 2})
    # ts diff only — strip it
    da = json.loads(a)
    db = json.loads(b)
    da["ts"] = db["ts"] = 0
    assert da == db


def test_invoice_pay_dispatches_webhook():
    """End-to-end: pay invoice → matching webhook fires."""
    from apps.invoices.tests.factories import InvoiceFactory
    user = UserFactory()
    Webhook.objects.create(user=user, url="https://x.example",
                           events="invoice.paid", secret="s", is_active=True)
    inv = InvoiceFactory(status="sent")
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.status = 200
        mock_open.return_value.__enter__.return_value.read.return_value = b""
        inv.mark_paid()
    delivery = WebhookDelivery.objects.get()
    assert delivery.event == "invoice.paid"
    assert delivery.payload["id"] == inv.id
