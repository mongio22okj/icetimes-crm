"""E2E coverage for Phase 7b pricing + support."""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_pricing_renders_three_tiers(page, server_url):
    page.goto(f"{server_url}/landing/pricing/")
    for tier in ["Starter", "Pro", "Enterprise"]:
        page.locator(f"main >> text={tier}").first.wait_for(state="visible", timeout=5000)


def test_support_form_submission_persists(page, server_url):
    from apps.marketing.models import SupportTicket
    assert SupportTicket.objects.count() == 0

    page.goto(f"{server_url}/landing/support/")
    page.fill("input[name='name']", "E2E Tester")
    page.fill("input[name='email']", "tester@example.com")
    page.fill("input[name='subject']", "E2E test ticket")
    page.fill("textarea[name='body']", "This is a test from playwright.")
    page.click("button:has-text('Send message')")

    # Success flash visible after redirect
    page.locator("text=we'll be in touch").first.wait_for(state="visible", timeout=5000)

    ticket = SupportTicket.objects.get()
    assert ticket.email == "tester@example.com"
    assert ticket.subject == "E2E test ticket"
