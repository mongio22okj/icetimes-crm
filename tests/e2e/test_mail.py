"""E2E coverage for Phase 5a Mail."""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_inbox_renders_seeded_mail(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/mail/inbox/")
    # At least one row visible in the message list
    rows = page.locator("section a[href*='/mail/'][href$='/']")
    rows.first.wait_for(state="visible", timeout=5000)
    assert rows.count() > 0


def test_compose_send_lands_on_sent(page, server_url):
    from apps.accounts.tests.factories import UserFactory
    recipient = UserFactory(username="recipient_e2e", is_staff=True)

    _login(page, server_url)
    page.goto(f"{server_url}/mail/compose/")
    # Select by value (PK) since label format is User.__str__
    page.locator("select[name='recipient']").select_option(value=str(recipient.pk))
    page.fill("input[name='subject']", "Hello from E2E test")
    page.fill("textarea[name='body']", "This is an automated test message.")
    page.click("button:has-text('Send')")

    # Lands on Sent folder
    page.wait_for_url(f"{server_url}/mail/sent/")
    page.locator("text=Hello from E2E test").first.wait_for(state="visible", timeout=5000)


def test_open_thread_marks_read_and_shows_reply_form(page, server_url):
    from django.contrib.auth import get_user_model

    from apps.accounts.tests.factories import UserFactory
    from apps.mail.tests.factories import MessageFactory

    User = get_user_model()
    demo = User.objects.get(username="demo")
    sender = UserFactory(username="thread_sender", is_staff=True)
    msg = MessageFactory(
        sender=sender, recipient=demo,
        subject="ThreadTestSubject", body="Hello from sender.",
        is_read=False,
    )

    _login(page, server_url)
    page.goto(f"{server_url}/mail/{msg.pk}/")
    # Subject visible in right pane
    page.locator("h1:has-text('ThreadTestSubject')").wait_for(state="visible", timeout=5000)
    # Reply form visible
    page.locator("textarea[name='body']").wait_for(state="visible", timeout=5000)


def test_reply_creates_visible_message_in_thread(page, server_url):
    from django.contrib.auth import get_user_model

    from apps.accounts.tests.factories import UserFactory
    from apps.mail.tests.factories import MessageFactory

    User = get_user_model()
    demo = User.objects.get(username="demo")
    sender = UserFactory(username="reply_sender", is_staff=True)
    msg = MessageFactory(
        sender=sender, recipient=demo,
        subject="ReplyableSubject", body="Care to respond?",
    )

    _login(page, server_url)
    page.goto(f"{server_url}/mail/{msg.pk}/")
    page.fill("textarea[name='body']", "Yes I will reply.")
    page.click("button:has-text('Send reply')")

    # Lands on the new reply's thread, body visible
    page.locator("text=Yes I will reply").first.wait_for(state="visible", timeout=5000)


def test_star_persists_on_inbox(page, server_url):
    from django.contrib.auth import get_user_model

    from apps.accounts.tests.factories import UserFactory
    from apps.mail.tests.factories import MessageFactory

    User = get_user_model()
    demo = User.objects.get(username="demo")
    sender = UserFactory(username="star_sender", is_staff=True)
    msg = MessageFactory(
        sender=sender, recipient=demo,
        subject="StarMeSubject", is_starred=False,
    )

    _login(page, server_url)
    page.goto(f"{server_url}/mail/{msg.pk}/")
    page.locator("button[title*='Star']").first.click()

    # Verify in DB
    msg.refresh_from_db()
    assert msg.is_starred is True
