"""E2E coverage for Phase 5b Chat."""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_chat_home_lists_seeded_conversations(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/chat/")
    # Conversations list visible (left sub-sidebar)
    rows = page.locator("aside ul li a")
    rows.first.wait_for(state="visible", timeout=5000)
    assert rows.count() > 0


def test_open_conversation_renders_bubbles(page, server_url):
    from django.contrib.auth import get_user_model

    from apps.accounts.tests.factories import UserFactory
    from apps.chat.tests.factories import ChatMessageFactory

    User = get_user_model()
    demo = User.objects.get(username="demo")
    partner = UserFactory(username="bubble_partner", is_staff=True)
    ChatMessageFactory(sender=partner, recipient=demo, body="UniqueBubbleText")

    _login(page, server_url)
    page.goto(f"{server_url}/chat/{partner.pk}/")
    # Stream container visible with the message body
    page.locator("#chat-stream").wait_for(state="visible", timeout=5000)
    page.locator("text=UniqueBubbleText").first.wait_for(state="visible", timeout=5000)


def test_send_message_appears_in_stream(page, server_url):
    from django.contrib.auth import get_user_model

    from apps.accounts.tests.factories import UserFactory

    User = get_user_model()
    demo = User.objects.get(username="demo")
    partner = UserFactory(username="send_partner", is_staff=True)

    _login(page, server_url)
    page.goto(f"{server_url}/chat/{partner.pk}/")
    page.fill("input[name='body']", "Hello from automation")
    page.click("button:has-text('Send')")

    page.wait_for_url(f"{server_url}/chat/{partner.pk}/")
    page.locator("text=Hello from automation").first.wait_for(state="visible", timeout=5000)
