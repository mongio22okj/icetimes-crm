# Phase 3 — Auth Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the verify-email flow and confirm-password "sudo mode" middleware, close the v0.1.0 known limitations on email verification and dev email delivery, and rewire the Phase 2 2FA destructive actions to use confirm-password instead of inline password inputs.

**Architecture:** Two new mixins (`EmailVerifiedRequiredMixin` and `PasswordConfirmationRequiredMixin`) slot next to `LoginRequiredMixin` on protected CBVs. Four new views under fresh URL namespaces (`/email/verify/*`, `/password/confirm/`). A single migration adds `email_verified_at` to `User`, backfills existing rows, and promotes `email` to `unique=True`. Uses Django's built-in `default_token_generator` and `send_mail` — no new deps.

**Tech Stack:** Django 5.1 · Tailwind v4 · Alpine.js 3.14 · pytest · Playwright.

**Reference spec:** [`docs/superpowers/specs/2026-04-23-phase3-auth-completion-design.md`](../specs/2026-04-23-phase3-auth-completion-design.md)

**6 commits:**
1. Email infra — model field, uniqueness, migration, seed
2. Verify-email views + templates + RegisterView plumbing
3. `EmailVerifiedRequiredMixin` + sweep across protected CBVs
4. Confirm-password infrastructure (mixin + view + template)
5. 2FA rewiring — Disable/Regenerate use PCRM, drop inline password inputs
6. E2E tests

---

## Pre-flight

- [ ] **Baseline: 143 unit + 10 E2E still green on main.**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: `143 passed`.

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/test_shell.py tests/e2e/test_settings.py -m e2e -q 2>&1 | tail -3`
Expected: `10 passed`.

- [ ] **Create feature branch.**

Run: `git switch -c phase3-auth-completion`
Expected: `Switched to a new branch 'phase3-auth-completion'`.

---

## Task 1 — Email infrastructure

**Files:**
- Modify: `apex/settings/dev.py` (console email backend)
- Modify: `apps/accounts/models.py` (email unique + email_verified_at + lowercase save)
- Create: `apps/accounts/migrations/0003_email_verification.py` (schema + backfill)
- Modify: `apps/core/management/commands/seed_demo.py` (mark seeded users verified; unique emails)
- Create: `apps/accounts/tests/test_user_model.py`

### Step 1.1 — Add console email backend to dev settings

Open `apex/settings/dev.py` and append (after the STORAGES block):

```python
# Print outbound email to the terminal in dev; verify links and password-reset
# links become visible in the runserver log.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "Apex Dashboard <noreply@apex.local>"
```

### Step 1.2 — Update User model

Open `apps/accounts/models.py`. Replace the User class body:

```python
class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("staff", "Staff"),
    ]
    email = models.EmailField(unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default="staff")
    bio = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)
```

Remove the old `# TODO: Make email unique ...` comment (the comment is resolved by this change). Keep the `from .two_factor import TwoFactorDevice` import at the bottom.

### Step 1.3 — Write model tests (TDD: failing first)

Create `apps/accounts/tests/test_user_model.py`:

```python
import pytest
from django.db import IntegrityError
from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_email_stored_lowercased_on_save():
    u = User.objects.create_user(username="alice", email="Alice@Example.com", password="pw")
    u.refresh_from_db()
    assert u.email == "alice@example.com"


def test_duplicate_email_raises_at_db_level():
    User.objects.create_user(username="one", email="dup@example.com", password="pw")
    with pytest.raises(IntegrityError):
        User.objects.create_user(username="two", email="dup@example.com", password="pw")


def test_case_insensitive_email_uniqueness():
    User.objects.create_user(username="one", email="alice@example.com", password="pw")
    with pytest.raises(IntegrityError):
        User.objects.create_user(username="two", email="Alice@EXAMPLE.com", password="pw")


def test_email_verified_at_defaults_to_none():
    u = User.objects.create_user(username="alice", email="alice@example.com", password="pw")
    assert u.email_verified_at is None
```

### Step 1.4 — Run the tests (they fail because migration hasn't run)

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_user_model.py -v 2>&1 | tail -15`
Expected: failures referring to the missing `email_verified_at` field or uniqueness not enforced.

### Step 1.5 — Generate the migration

Run: `/Users/silkalns/.local/bin/uv run python manage.py makemigrations accounts 2>&1 | tail -10`
Expected: `Migrations for 'accounts':  apps/accounts/migrations/0003_...` mentioning `email_verified_at` added and `email` altered to unique.

Open the generated file. Django won't include a data-backfill op by default — we need to add one between the AddField and AlterField ops, otherwise `AlterField(unique=True)` will fail on any DB with duplicate or blank emails.

Rewrite the migration file as:

```python
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_emails(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    seen = set()
    now = timezone.now()
    for u in User.objects.order_by("pk"):
        email = (u.email or "").strip().lower()
        if not email:
            email = f"{u.username}@apex.local"
        if email in seen:
            email = f"{u.username}+{u.pk}@apex.local"
        u.email = email
        seen.add(email)
        # Seeded users are already trusted — mark verified so dev isn't interrupted.
        if not u.email_verified_at:
            u.email_verified_at = now
        u.save(update_fields=["email", "email_verified_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_twofactordevice"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_emails, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(max_length=254, unique=True),
        ),
    ]
```

Name the file `apps/accounts/migrations/0003_email_verification.py` (rename from the makemigrations-generated name if different).

### Step 1.6 — Apply migration

Run: `/Users/silkalns/.local/bin/uv run python manage.py migrate accounts 2>&1 | tail -5`
Expected: `Applying accounts.0003_email_verification... OK`.

### Step 1.7 — Update `seed_demo.py`

Open `apps/core/management/commands/seed_demo.py`. Modify so:

- Demo user gets `email_verified_at = timezone.now()`
- Factory users all get verified AND unique emails (append `+<index>` so uniqueness holds across the batch)

Replace the existing `handle` method with:

```python
    def handle(self, *args, **opts):
        from django.utils import timezone

        User = get_user_model()

        # 1. Demo user with known credentials (idempotent via get_or_create)
        demo, created = User.objects.get_or_create(
            username="demo",
            defaults={
                "email": "demo@example.com",
                "first_name": "Demo",
                "last_name": "User",
                "role": "admin",
                "is_staff": True,
            },
        )
        demo.set_password("demo1234")
        demo.email_verified_at = timezone.now()
        demo.save()

        # 2. Batch users via factory (randomized, password="password").
        # Factory-produced emails might collide; suffix each with +<index> and
        # mark verified so the fixture doesn't need the verify flow.
        for i in range(15):
            u = UserFactory()
            base, _, domain = u.email.partition("@")
            u.email = f"{base}+{i}@{domain or 'apex.local'}"
            u.email_verified_at = timezone.now()
            u.save(update_fields=["email", "email_verified_at"])

        # 3. Categories + products
        CategoryFactory.create_batch(5)
        ProductFactory.create_batch(25)

        # 4. Orders with items
        for _ in range(30):
            order = OrderFactory()
            for _ in range(3):
                OrderItemFactory(order=order)

        self.stdout.write(self.style.SUCCESS("Seeded. Demo login: demo / demo1234"))
```

Confirm the final `SUCCESS` message format matches what `tests/e2e/conftest.py` expects — currently it prints to stdout during E2E setup. If it differs, match the existing format.

### Step 1.8 — Re-run model tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_user_model.py -v 2>&1 | tail -10`
Expected: 4 passed.

### Step 1.9 — Run full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: 147 passed (143 + 4).

If a previously-passing test fails with a `UNIQUE constraint failed` on `email` or a "email must be unique" error, that's likely `UserFactory` defaulting to colliding emails. In `apps/accounts/tests/factories.py`, ensure `email` uses `factory.Sequence(lambda n: f"user{n}@example.com")` (or similar unique generator). Report if this emerges.

### Step 1.10 — Commit

```bash
git add apex/settings/dev.py apps/accounts/models.py apps/accounts/migrations/0003_email_verification.py apps/core/management/commands/seed_demo.py apps/accounts/tests/test_user_model.py
git commit -m "$(cat <<'EOF'
feat(accounts): email uniqueness + email_verified_at + console backend

Adds User.email unique=True, email_verified_at nullable timestamp, and
case-insensitive lowercased storage via save() override. Migration
0003 backfills blanks/dups safely before enforcing uniqueness.

Dev settings gain console email backend so verify + password-reset
emails print to the runserver log. Seed demo sets email_verified_at
for the demo user and all 15 factory users.

4 new unit tests: lowercased on save, DB-level dup raises, case
insensitive collision, email_verified_at defaults to None.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — Verify-email views + templates + RegisterView plumbing

**Files:**
- Create: `apps/accounts/verify_email.py` (send helper)
- Modify: `apps/accounts/views.py` (RegisterView + 3 new views + imports)
- Modify: `apex/urls.py` (3 new URL patterns)
- Create: `templates/registration/email_verify_prompt.html`
- Create: `templates/registration/email_verify_invalid.html`
- Create: `templates/registration/email_verify_email.txt`
- Create: `templates/registration/email_verify_email.html`
- Create: `apps/accounts/tests/test_verify_email.py`

### Step 2.1 — Create the email-sending helper

`apps/accounts/verify_email.py`:

```python
"""Token + email helpers for the email-verification flow.

Uses Django's default_token_generator (same primitive behind password reset).
"""
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def build_verify_url(user, request) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return request.build_absolute_uri(
        reverse("email_verify_confirm", kwargs={"uidb64": uidb64, "token": token})
    )


def send_verify_email(user, request) -> None:
    verify_url = build_verify_url(user, request)
    context = {"user": user, "verify_url": verify_url, "site_name": "Apex Dashboard"}
    body_txt = render_to_string("registration/email_verify_email.txt", context)
    body_html = render_to_string("registration/email_verify_email.html", context)
    send_mail(
        subject="Verify your Apex Dashboard email",
        message=body_txt,
        from_email=None,  # uses DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
        html_message=body_html,
    )
```

### Step 2.2 — Failing tests

Create `apps/accounts/tests/test_verify_email.py`:

```python
import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_register_creates_unverified_user(client):
    mail.outbox = []
    response = client.post("/accounts/register/", {
        "username": "bob",
        "email": "bob@example.com",
        "first_name": "Bob",
        "last_name": "Builder",
        "password1": "testpass-x9!",
        "password2": "testpass-x9!",
    })
    assert response.status_code == 302
    assert response["Location"].endswith("/email/verify/")
    from apps.accounts.models import User
    u = User.objects.get(username="bob")
    assert u.email_verified_at is None
    assert len(mail.outbox) == 1
    assert "verify" in mail.outbox[0].body.lower()
    # URL printed in the body should resolve against our host
    assert "/email/verify/" in mail.outbox[0].body


def test_verify_prompt_accessible_to_logged_in_unverified_user(client):
    user = UserFactory(email="alice@x.com")
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    response = client.get("/email/verify/")
    assert response.status_code == 200
    assert b"Check your email" in response.content or b"check your email" in response.content


def test_verify_prompt_redirects_already_verified_user_home(client):
    user = UserFactory()  # factory leaves email_verified_at=None by default
    from django.utils import timezone
    user.email_verified_at = timezone.now()
    user.save()
    client.force_login(user)
    response = client.get("/email/verify/")
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_confirm_view_with_valid_token_marks_verified(client):
    user = UserFactory(email="alice@x.com")
    user.email_verified_at = None
    user.save()
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    response = client.get(f"/email/verify/{uidb64}/{token}/")
    user.refresh_from_db()
    assert user.email_verified_at is not None
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_confirm_view_with_bad_token_renders_invalid_page(client):
    user = UserFactory(email="alice@x.com")
    user.email_verified_at = None
    user.save()
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    response = client.get(f"/email/verify/{uidb64}/not-a-valid-token/")
    assert response.status_code == 200
    assert b"expired" in response.content.lower() or b"invalid" in response.content.lower()
    user.refresh_from_db()
    assert user.email_verified_at is None


def test_confirm_view_idempotent_when_already_verified(client):
    user = UserFactory(email="alice@x.com")
    from django.utils import timezone
    user.email_verified_at = timezone.now()
    user.save()
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    response = client.get(f"/email/verify/{uidb64}/{token}/")
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_confirm_view_with_unknown_uid_renders_invalid_page(client):
    response = client.get("/email/verify/99999999/whatever/")
    assert response.status_code == 200
    assert b"expired" in response.content.lower() or b"invalid" in response.content.lower()


def test_resend_sends_new_email(client):
    user = UserFactory(email="alice@x.com")
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    mail.outbox = []
    response = client.post("/email/verify/resend/")
    assert response.status_code == 302
    assert len(mail.outbox) == 1


def test_resend_respects_cooldown(client):
    user = UserFactory(email="alice@x.com")
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    # First resend goes through
    client.post("/email/verify/resend/")
    mail.outbox = []
    # Second immediate resend is rate-gated
    client.post("/email/verify/resend/")
    assert len(mail.outbox) == 0
```

### Step 2.3 — Confirm tests fail

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_verify_email.py -v 2>&1 | tail -20`
Expected: 9 failures or errors (views don't exist yet, URL reverse fails).

### Step 2.4 — Add views in `apps/accounts/views.py`

At the top of the file (merge with existing imports — do not add duplicates):

```python
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from .verify_email import send_verify_email
```

Append these views to the bottom of the file:

```python
class EmailVerifyPromptView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.email_verified_at is not None:
            return redirect("/")
        sent_at = request.session.get("verify_email_sent_at")
        return render(request, "registration/email_verify_prompt.html", {
            "recent_send": bool(sent_at),
        })


class EmailVerifyResendView(LoginRequiredMixin, View):
    COOLDOWN_SECONDS = 60

    def post(self, request):
        import datetime
        stamp = request.session.get("verify_email_sent_at")
        now = timezone.now()
        if stamp:
            try:
                last = datetime.datetime.fromisoformat(stamp)
                if (now - last).total_seconds() < self.COOLDOWN_SECONDS:
                    messages.info(request, "Please wait a moment before requesting another link.")
                    return redirect("email_verify_prompt")
            except (ValueError, TypeError):
                pass
        send_verify_email(request.user, request)
        request.session["verify_email_sent_at"] = now.isoformat()
        messages.success(request, "A new verification link was sent.")
        return redirect("email_verify_prompt")


class EmailVerifyConfirmView(View):
    def get(self, request, uidb64, token):
        User_ = get_user_model()
        try:
            uid = int(force_str(urlsafe_base64_decode(uidb64)))
        except (ValueError, TypeError):
            return render(request, "registration/email_verify_invalid.html")
        user = User_.objects.filter(pk=uid).first()
        if user is None:
            return render(request, "registration/email_verify_invalid.html")
        # Idempotent: already verified → success redirect
        if user.email_verified_at is not None:
            messages.success(request, "Your email is already verified.")
            return redirect("/")
        if not default_token_generator.check_token(user, token):
            return render(request, "registration/email_verify_invalid.html")
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
        if not request.user.is_authenticated:
            user.backend = settings.AUTHENTICATION_BACKENDS[0]
            auth_login(request, user)
        messages.success(request, "Email verified — you're all set.")
        return redirect("/")
```

### Step 2.5 — Update `RegisterView.post`

Modify `RegisterView.post` to send a verify email and redirect to the prompt:

```python
    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            send_verify_email(user, request)
            request.session["verify_email_sent_at"] = timezone.now().isoformat()
            return redirect("email_verify_prompt")
        return render(request, "accounts/register.html", {"form": form})
```

### Step 2.6 — Wire URLs in `apex/urls.py`

Add to the imports:

```python
from apps.accounts.views import (
    TwoFactorAwareLoginView,
    TwoFactorChallengeView,
    EmailVerifyPromptView,
    EmailVerifyConfirmView,
    EmailVerifyResendView,
)
```

Add to `urlpatterns` (place the three new email-verify routes right after the 2FA challenge route):

```python
    path("email/verify/", EmailVerifyPromptView.as_view(), name="email_verify_prompt"),
    path("email/verify/resend/", EmailVerifyResendView.as_view(), name="email_verify_resend"),
    path("email/verify/<uidb64>/<token>/", EmailVerifyConfirmView.as_view(), name="email_verify_confirm"),
```

Order matters: `resend/` must come before the `<uidb64>/<token>/` pattern so `resend` doesn't get captured as a uid.

### Step 2.7 — Templates

`templates/registration/email_verify_prompt.html`:

```html
{% extends "layouts/auth.html" %}
{% block title %}Verify email · Apex{% endblock %}
{% block auth_content %}
<h1 class="text-2xl font-bold tracking-tight mb-1">Check your email</h1>
<p class="text-sm text-muted-foreground mb-6">
  We sent a verification link to <strong>{{ user.email }}</strong>. Click it to finish setting up your account.
</p>

{% if messages %}
  {% for message in messages %}
    <div class="mb-4 rounded-md border border-border bg-muted p-3 text-sm">{{ message }}</div>
  {% endfor %}
{% endif %}

<form method="post" action="{% url 'email_verify_resend' %}" class="space-y-3">
  {% csrf_token %}
  <button type="submit" class="w-full h-10 rounded-md bg-primary text-primary-foreground font-medium">
    Resend verification email
  </button>
</form>

<div class="mt-4 flex items-center justify-between text-sm">
  <span class="text-muted-foreground">Wrong address?</span>
  <form method="post" action="{% url 'logout' %}">
    {% csrf_token %}
    <button type="submit" class="text-primary hover:underline">Sign out</button>
  </form>
</div>
{% endblock %}
```

`templates/registration/email_verify_invalid.html`:

```html
{% extends "layouts/auth.html" %}
{% block title %}Link expired · Apex{% endblock %}
{% block auth_content %}
<h1 class="text-2xl font-bold tracking-tight mb-1">Link expired</h1>
<p class="text-sm text-muted-foreground mb-6">This verification link is invalid or has expired.</p>

{% if user.is_authenticated %}
  <form method="post" action="{% url 'email_verify_resend' %}">
    {% csrf_token %}
    <button type="submit" class="w-full h-10 rounded-md bg-primary text-primary-foreground font-medium">
      Request a new link
    </button>
  </form>
{% else %}
  <a href="{% url 'login' %}" class="w-full h-10 rounded-md bg-primary text-primary-foreground font-medium inline-flex items-center justify-center">Sign in</a>
{% endif %}
{% endblock %}
```

`templates/registration/email_verify_email.txt`:

```
Hi {{ user.first_name|default:user.username }},

Welcome to {{ site_name }}. Confirm your email address by clicking the link below:

{{ verify_url }}

If you didn't create an account, you can safely ignore this message.
```

`templates/registration/email_verify_email.html`:

```html
<!doctype html>
<html lang="en">
<body style="font-family: system-ui, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 16px; color: #0f172a;">
  <h1 style="font-size: 20px; margin: 0 0 16px;">Verify your {{ site_name }} email</h1>
  <p style="margin: 0 0 16px; font-size: 14px; line-height: 1.5;">
    Hi {{ user.first_name|default:user.username }},
  </p>
  <p style="margin: 0 0 24px; font-size: 14px; line-height: 1.5;">
    Confirm your email address to finish setting up your account.
  </p>
  <p style="margin: 0 0 24px;">
    <a href="{{ verify_url }}" style="display: inline-block; background: #16a34a; color: white; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 14px;">Verify email</a>
  </p>
  <p style="margin: 0 0 8px; font-size: 12px; color: #64748b;">Or paste this link into your browser:</p>
  <p style="margin: 0 0 24px; font-size: 12px; color: #64748b; word-break: break-all;">{{ verify_url }}</p>
  <p style="margin: 0; font-size: 12px; color: #64748b;">If you didn't create an account, you can safely ignore this message.</p>
</body>
</html>
```

### Step 2.8 — Run the tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_verify_email.py -v 2>&1 | tail -25`
Expected: 9 passed.

### Step 2.9 — Regression check

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: 156 passed (147 + 9). Some existing tests may need adjustments if `RegisterView` used to redirect to `LOGIN_REDIRECT_URL` — find and update them. Likely the existing `test_auth_flow.py` has a register-then-dashboard assertion.

If a test like `test_register_redirects_to_login_redirect_url` exists, change it to expect `/email/verify/` or drop it (replaced by our new test).

### Step 2.10 — Rebuild Tailwind

Run: `npm run build 2>&1 | tail -2`
Expected: `Done in ...ms`.

### Step 2.11 — Commit

```bash
git add apps/accounts/verify_email.py apps/accounts/views.py apex/urls.py templates/registration/email_verify_prompt.html templates/registration/email_verify_invalid.html templates/registration/email_verify_email.txt templates/registration/email_verify_email.html apps/accounts/tests/test_verify_email.py apps/accounts/tests/test_auth_flow.py
git commit -m "$(cat <<'EOF'
feat(accounts): verify-email flow (prompt, confirm, resend)

After registration, send a verification email with a tokenized link
and redirect to /email/verify/ (not straight to the dashboard).
Confirm view is idempotent — a second click on a valid link for an
already-verified account flashes success and redirects home.

Resend is rate-gated to 60 seconds per session. Links use Django's
default_token_generator (same primitive as password reset).

9 unit tests cover register → unverified + email sent, prompt access,
valid/bad/idempotent token paths, and resend cooldown.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — EmailVerifiedRequiredMixin + sweep

**Files:**
- Create: `apps/accounts/mixins.py` (new home for `EmailVerifiedRequiredMixin`; Phase 4+ may add more)
- Modify: every protected CBV across `apps/dashboard/views.py`, `apps/orders/views.py`, `apps/products/views.py`, `apps/accounts/views.py`
- Create: `apps/accounts/tests/test_email_verified_mixin.py`

### Step 3.1 — Create the mixin

`apps/accounts/mixins.py`:

```python
"""Auth mixins that slot next to LoginRequiredMixin on protected CBVs."""
from django.shortcuts import redirect


class EmailVerifiedRequiredMixin:
    """Requires user.email_verified_at is set. Must be paired with LoginRequiredMixin
    (authenticated checks happen there; this mixin only enforces verification)."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.email_verified_at is None:
            return redirect("email_verify_prompt")
        return super().dispatch(request, *args, **kwargs)
```

### Step 3.2 — Write failing tests

Create `apps/accounts/tests/test_email_verified_mixin.py`:

```python
import pytest
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_unverified_user_redirected_from_dashboard(client):
    user = UserFactory()
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"].endswith("/email/verify/")


def test_unverified_user_redirected_from_orders(client):
    user = UserFactory()
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    response = client.get("/orders/")
    assert response.status_code == 302
    assert response["Location"].endswith("/email/verify/")


def test_unverified_user_can_access_verify_prompt(client):
    user = UserFactory()
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    response = client.get("/email/verify/")
    assert response.status_code == 200


def test_unverified_user_can_logout(client):
    user = UserFactory()
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    response = client.post("/accounts/logout/")
    assert response.status_code == 302  # goes to login, not email-verify
    assert "/accounts/login/" in response["Location"] or response["Location"] == "/"


def test_verified_user_reaches_dashboard(client):
    from django.utils import timezone
    user = UserFactory()
    user.email_verified_at = timezone.now()
    user.save()
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 200
```

### Step 3.3 — Confirm tests fail

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_email_verified_mixin.py -v 2>&1 | tail -15`
Expected: the "redirected from dashboard/orders" tests fail because no gate exists yet.

### Step 3.4 — Apply mixin to every protected CBV

The sweep: wherever `LoginRequiredMixin` appears on a class that's part of the dashboard flow, add `EmailVerifiedRequiredMixin` right AFTER it. Both together in MRO:

```python
class SomeView(BreadcrumbsMixin, EmailVerifiedRequiredMixin, LoginRequiredMixin, ...):
```

Rationale for MRO order: `LoginRequiredMixin` first catches anonymous users. `EmailVerifiedRequiredMixin` then catches unverified logged-in users. `BreadcrumbsMixin` (which runs get_context_data, not dispatch) doesn't interfere.

Wait — actually `LoginRequiredMixin.dispatch` runs super(), which means our mixin's dispatch runs BEFORE the login check if we put it first. Put it AFTER:

```python
class SomeView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    ...
```

With this order: `BreadcrumbsMixin.get_context_data` wraps the response, `LoginRequiredMixin.dispatch` runs first (catches anon), THEN `EmailVerifiedRequiredMixin.dispatch` runs (catches unverified), THEN the generic view runs.

Edit these files to add `EmailVerifiedRequiredMixin` to each CBV's base tuple (after `LoginRequiredMixin`):

**`apps/dashboard/views.py`** — `DashboardView` uses `@method_decorator(login_required)` instead of the mixin, so a different tactic is needed:
- Swap the function-decorator to class mixins. Replace:
  ```python
  @method_decorator(login_required, name="dispatch")
  class DashboardView(View):
  ```
  with:
  ```python
  from django.contrib.auth.mixins import LoginRequiredMixin
  from apps.accounts.mixins import EmailVerifiedRequiredMixin

  class DashboardView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
  ```
- Keep `@login_required` on the `revenue_chart_data` FBV as-is (function views aren't covered by the mixin; they just need to render; the dashboard URL handles the verify gate).

**`apps/orders/views.py`** — add `from apps.accounts.mixins import EmailVerifiedRequiredMixin` and insert the mixin into every CBV's bases tuple, between `LoginRequiredMixin` and the generic view. Four classes: `OrderListView`, `OrderDetailView`, `OrderCreateView`, `OrderUpdateView`.

**`apps/products/views.py`** — same treatment. Four classes: `ProductListView`, `ProductDetailView`, `ProductCreateView`, `ProductUpdateView`.

**`apps/accounts/views.py`** — insert on the view classes that SHOULD be gated:
- `UserListView`, `UserDetailView`, `UserCreateView`, `UserUpdateView` (all have `LoginRequiredMixin + StaffRequiredMixin` — add `EmailVerifiedRequiredMixin` after `LoginRequiredMixin`)
- `ProfileView`
- `PasswordChangeView`
- `AppearanceView`
- `TwoFactorView`
- `TwoFactorEnableView`
- `TwoFactorSetupView`
- `TwoFactorDisableView`
- `TwoFactorRegenerateView`

Do NOT add to: `RegisterView`, `EmailVerifyPromptView`, `EmailVerifyConfirmView`, `EmailVerifyResendView`, `TwoFactorChallengeView`, `TwoFactorAwareLoginView`.

### Step 3.5 — Run mixin tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_email_verified_mixin.py -v 2>&1 | tail -15`
Expected: 5 passed.

### Step 3.6 — Run full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: 161 passed (156 + 5).

If other tests fail, it's likely they create a user without setting `email_verified_at` and then hit a protected view. Fix the test fixtures by either:
- Setting `email_verified_at = timezone.now()` on the user, OR
- Using a helper that creates verified users (consider adding a `VerifiedUserFactory` to `apps/accounts/tests/factories.py`, or change the default in `UserFactory`).

Cleanest fix: update `UserFactory` so `email_verified_at` defaults to `timezone.now()`. Tests that need an unverified user can override per-call. This mirrors the seed behavior.

If `UserFactory` is updated, re-run the verify-email tests to ensure their explicit unverified setup still works.

### Step 3.7 — Commit

```bash
git add apps/accounts/mixins.py apps/dashboard/views.py apps/orders/views.py apps/products/views.py apps/accounts/views.py apps/accounts/tests/test_email_verified_mixin.py apps/accounts/tests/factories.py
git commit -m "$(cat <<'EOF'
feat(accounts): EmailVerifiedRequiredMixin + sweep across protected CBVs

Mixin redirects logged-in-but-unverified users to /email/verify/
on every protected view. Slotted between LoginRequiredMixin and
the generic view in the bases tuple so the anon check still runs first.

DashboardView converts from @login_required function-decorator to
class-based LoginRequiredMixin + new gate.

UserFactory now defaults email_verified_at=now() so test fixtures
don't trip the gate; verify-email tests explicitly clear it.

5 unit tests cover the gate for dashboard, orders, the verify-prompt
exemption, logout, and the verified happy path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Confirm-password infrastructure

**Files:**
- Modify: `apps/accounts/mixins.py` (add `PasswordConfirmationRequiredMixin`)
- Modify: `apps/accounts/views.py` (add `ConfirmPasswordView`)
- Modify: `apex/urls.py` (add `/password/confirm/` route)
- Create: `templates/registration/confirm_password.html`
- Create: `apps/accounts/tests/test_confirm_password.py`

### Step 4.1 — Add mixin

Append to `apps/accounts/mixins.py`:

```python
from datetime import datetime, timedelta
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


class PasswordConfirmationRequiredMixin:
    """Re-challenge user's password on sensitive actions. 3-hour grace.

    Place AFTER LoginRequiredMixin in the bases tuple so unauthenticated
    users redirect to login, not to a confirm page they can't reach.
    """
    password_confirmation_max_age = timedelta(hours=3)

    def dispatch(self, request, *args, **kwargs):
        if not self._is_confirmed(request):
            return redirect(f"{reverse('confirm_password')}?next={request.get_full_path()}")
        return super().dispatch(request, *args, **kwargs)

    def _is_confirmed(self, request) -> bool:
        stamp = request.session.get("password_confirmed_at")
        if not stamp:
            return False
        try:
            confirmed_at = datetime.fromisoformat(stamp)
        except (ValueError, TypeError):
            return False
        return timezone.now() - confirmed_at < self.password_confirmation_max_age
```

### Step 4.2 — Write failing tests

Create `apps/accounts/tests/test_confirm_password.py`:

```python
from datetime import timedelta
import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _verified_user(password="testpass-x9!"):
    user = UserFactory()
    user.email_verified_at = timezone.now()
    user.set_password(password)
    user.save()
    return user


def test_confirm_password_renders_form(client):
    user = _verified_user()
    client.force_login(user)
    response = client.get("/password/confirm/")
    assert response.status_code == 200
    assert b"Confirm password" in response.content


def test_confirm_password_correct_sets_session_and_redirects(client):
    user = _verified_user(password="mypass-9")
    client.force_login(user)
    response = client.post("/password/confirm/", {
        "password": "mypass-9",
        "next": "/orders/",
    })
    assert response.status_code == 302
    assert response["Location"] == "/orders/"
    assert "password_confirmed_at" in client.session


def test_confirm_password_wrong_stays_on_form(client):
    user = _verified_user(password="good")
    client.force_login(user)
    response = client.post("/password/confirm/", {
        "password": "WRONG",
        "next": "/",
    })
    assert response.status_code == 200
    assert "password_confirmed_at" not in client.session


def test_confirm_password_rejects_external_next(client):
    user = _verified_user(password="good")
    client.force_login(user)
    response = client.post("/password/confirm/", {
        "password": "good",
        "next": "https://evil.example.com/",
    })
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_grace_expires_after_3_hours():
    from apps.accounts.mixins import PasswordConfirmationRequiredMixin
    mixin = PasswordConfirmationRequiredMixin()
    # Simulate a stale session
    class FakeRequest:
        session = {"password_confirmed_at": (timezone.now() - timedelta(hours=4)).isoformat()}
    assert not mixin._is_confirmed(FakeRequest())


def test_fresh_grace_recognized():
    from apps.accounts.mixins import PasswordConfirmationRequiredMixin
    mixin = PasswordConfirmationRequiredMixin()
    class FakeRequest:
        session = {"password_confirmed_at": timezone.now().isoformat()}
    assert mixin._is_confirmed(FakeRequest())
```

### Step 4.3 — Confirm tests fail

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_confirm_password.py -v 2>&1 | tail -15`
Expected: 6 failures (view + URL don't exist).

### Step 4.4 — Add view

In `apps/accounts/views.py`, add to the top-of-file imports:
```python
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import PasswordConfirmForm  # (already imported if Phase 2's Task 4 was committed)
```

Append:

```python
class ConfirmPasswordView(LoginRequiredMixin, View):
    template_name = "registration/confirm_password.html"

    def get(self, request):
        return render(request, self.template_name, {
            "form": PasswordConfirmForm(user=request.user),
            "next": request.GET.get("next", "/"),
        })

    def post(self, request):
        form = PasswordConfirmForm(request.POST, user=request.user)
        next_url = request.POST.get("next") or "/"
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = "/"
        if form.is_valid():
            request.session["password_confirmed_at"] = timezone.now().isoformat()
            return HttpResponseRedirect(next_url)
        return render(request, self.template_name, {"form": form, "next": next_url})
```

### Step 4.5 — Wire URL

In `apex/urls.py` add to the imports:
```python
from apps.accounts.views import ConfirmPasswordView
```

Add to `urlpatterns` (near the email-verify routes):
```python
    path("password/confirm/", ConfirmPasswordView.as_view(), name="confirm_password"),
```

### Step 4.6 — Create `templates/registration/confirm_password.html`

```html
{% extends "layouts/auth.html" %}
{% block title %}Confirm password · Apex{% endblock %}
{% block auth_content %}
<h1 class="text-2xl font-bold tracking-tight mb-1">Confirm password</h1>
<p class="text-sm text-muted-foreground mb-6">This is a secure area. Please confirm your password to continue.</p>

<form method="post" class="space-y-4">
  {% csrf_token %}
  <input type="hidden" name="next" value="{{ next }}">
  <div>
    <label for="{{ form.password.id_for_label }}" class="block text-sm font-medium mb-1.5">Password</label>
    {{ form.password }}
    {% if form.password.errors %}<p class="text-xs text-destructive mt-1">{{ form.password.errors.0 }}</p>{% endif %}
  </div>
  <button type="submit" class="w-full h-10 rounded-md bg-primary text-primary-foreground font-medium">Confirm password</button>
</form>

<div class="mt-4 text-sm text-center">
  <a href="{% url 'settings:profile' %}" class="text-muted-foreground hover:text-primary">Back to settings</a>
</div>
{% endblock %}
```

### Step 4.7 — Run tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_confirm_password.py -v 2>&1 | tail -15`
Expected: 6 passed.

### Step 4.8 — Full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: 167 passed (161 + 6).

### Step 4.9 — Rebuild Tailwind

Run: `npm run build 2>&1 | tail -2`

### Step 4.10 — Commit

```bash
git add apps/accounts/mixins.py apps/accounts/views.py apex/urls.py templates/registration/confirm_password.html apps/accounts/tests/test_confirm_password.py
git commit -m "$(cat <<'EOF'
feat(accounts): confirm-password mixin + view (sudo mode)

PasswordConfirmationRequiredMixin redirects views without a fresh
session grace to /password/confirm/?next=<path>. ConfirmPasswordView
validates via Phase 2's PasswordConfirmForm; on success sets
session.password_confirmed_at and redirects to next (url_has_allowed
_host_and_scheme guard stops open redirects). Grace window is 3h.

6 unit tests cover the form, success/failure, grace expiry, fresh
grace, and the external-next safeguard.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — 2FA rewiring

**Files:**
- Modify: `apps/accounts/views.py` (TwoFactorDisableView, TwoFactorRegenerateView)
- Modify: `templates/settings/two_factor.html` (drop inline password inputs)
- Modify: `apps/accounts/tests/test_two_factor_views.py` (tests that post `password=` now need a confirm-password pre-step)

### Step 5.1 — Rewrite the two views

In `apps/accounts/views.py`, update the imports:
```python
from apps.accounts.mixins import EmailVerifiedRequiredMixin, PasswordConfirmationRequiredMixin
```

Replace `TwoFactorDisableView` with:

```python
class TwoFactorDisableView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                           PasswordConfirmationRequiredMixin, View):
    def post(self, request):
        TwoFactorDevice.objects.filter(user=request.user).delete()
        messages.success(request, "Two-factor authentication disabled.")
        return redirect("settings:two_factor")
```

Replace `TwoFactorRegenerateView` with:

```python
class TwoFactorRegenerateView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                              PasswordConfirmationRequiredMixin, View):
    def post(self, request):
        device = TwoFactorDevice.objects.filter(user=request.user, confirmed=True).first()
        if device:
            codes = device.generate_recovery_codes()
            request.session["_2fa_recovery_codes"] = codes
            messages.success(request, "New recovery codes generated.")
        return redirect("settings:two_factor")
```

No more `PasswordConfirmForm` usage inside these views. The inline password check is gone; the PCRM mixin handles it.

### Step 5.2 — Update template

In `templates/settings/two_factor.html` — find the "confirmed" section and replace the two forms-with-password-inputs with bare POST forms:

Replace:

```html
    <form method="post" action="{% url 'settings:two_factor_regenerate' %}" class="mt-6 flex items-end gap-3">
      {% csrf_token %}
      <div class="flex-1">
        <label class="block text-sm font-medium mb-1.5">Password</label>
        <input type="password" name="password" required autocomplete="current-password"
               class="...">
      </div>
      <button type="submit" class="...">Regenerate codes</button>
    </form>

    <form method="post" action="{% url 'settings:two_factor_disable' %}" class="mt-4 flex items-end gap-3">
      {% csrf_token %}
      <div class="flex-1">
        <label class="block text-sm font-medium mb-1.5">Confirm password to disable</label>
        <input type="password" name="password" required autocomplete="current-password"
               class="...">
      </div>
      <button type="submit" class="...">Disable 2FA</button>
    </form>
```

With:

```html
    <div class="mt-6 flex flex-wrap gap-3">
      <form method="post" action="{% url 'settings:two_factor_regenerate' %}">
        {% csrf_token %}
        <button type="submit"
                class="h-10 px-3 rounded-md border border-border inline-flex items-center text-sm hover:bg-accent">
          Regenerate codes
        </button>
      </form>
      <form method="post" action="{% url 'settings:two_factor_disable' %}">
        {% csrf_token %}
        <button type="submit"
                class="h-10 px-3 rounded-md border border-destructive text-destructive inline-flex items-center text-sm hover:bg-destructive hover:text-destructive-foreground transition-colors">
          Disable 2FA
        </button>
      </form>
    </div>
    <p class="mt-4 text-xs text-muted-foreground">You'll be asked to re-enter your password before disabling or regenerating codes.</p>
```

### Step 5.3 — Update existing 2FA view tests

Phase 2's `apps/accounts/tests/test_two_factor_views.py` has tests that POST a `password=` form to disable/regenerate routes. With PCRM, those POSTs now redirect to `/password/confirm/` first (because no `password_confirmed_at` in session).

Update the affected tests to set the session grace before the disable POST:

```python
def _confirm_password_session(client):
    """Inject a fresh confirm-password grace into the session."""
    from django.utils import timezone
    session = client.session
    session["password_confirmed_at"] = timezone.now().isoformat()
    session.save()
```

Then in `test_disable_requires_password`, `test_regenerate_requires_password`, and `test_regenerate_replaces_codes_when_password_correct`:

- Replace the "wrong password → device still exists" assertions with "no grace → redirected to confirm".
- Replace the "correct password → device deleted" path with `_confirm_password_session(client)` followed by the POST (no `password=` payload).

Refactored tests (replace the three existing ones):

```python
def test_disable_without_confirm_grace_redirects(client):
    user = _login_user(client)
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    response = client.post("/settings/two-factor/disable/")
    assert response.status_code == 302
    assert "/password/confirm/" in response["Location"]
    assert TwoFactorDevice.objects.filter(user=user).exists()


def test_disable_with_confirm_grace_deletes_device(client):
    user = _login_user(client)
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    _confirm_password_session(client)
    response = client.post("/settings/two-factor/disable/")
    assert response.status_code == 302
    assert not TwoFactorDevice.objects.filter(user=user).exists()


def test_regenerate_without_confirm_grace_redirects(client):
    user = _login_user(client)
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    original_codes = d.generate_recovery_codes()
    response = client.post("/settings/two-factor/regenerate/")
    assert response.status_code == 302
    assert "/password/confirm/" in response["Location"]
    d.refresh_from_db()
    original_hashes = {e["hash"] for e in d.recovery_codes}
    import hashlib
    assert original_hashes == {
        hashlib.sha256(c.upper().encode()).hexdigest() for c in original_codes
    }


def test_regenerate_with_confirm_grace_replaces_codes(client):
    user = _login_user(client)
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    original_codes = d.generate_recovery_codes()
    _confirm_password_session(client)
    response = client.post("/settings/two-factor/regenerate/")
    d.refresh_from_db()
    new_hashes = {e["hash"] for e in d.recovery_codes}
    import hashlib
    original_hashes = {
        hashlib.sha256(c.upper().encode()).hexdigest() for c in original_codes
    }
    assert new_hashes != original_hashes
    assert len(d.recovery_codes) == 8
```

Add the helper at the top of the test file:
```python
def _confirm_password_session(client):
    from django.utils import timezone
    session = client.session
    session["password_confirmed_at"] = timezone.now().isoformat()
    session.save()
```

Also update the earlier `test_enable_ignored_when_already_confirmed` — it posts with `password="mypass-9"` but the enable view still takes password inline (not changed in this task). Keep that test as-is.

### Step 5.4 — Run affected tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_two_factor_views.py -v 2>&1 | tail -25`
Expected: all tests pass (count may shift: 13 was the baseline for 2FA views; may be slightly different after the rewrite — report exact pass count).

### Step 5.5 — Full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: still 167+ (no lost coverage).

### Step 5.6 — Rebuild Tailwind

Run: `npm run build 2>&1 | tail -2`

### Step 5.7 — Commit

```bash
git add apps/accounts/views.py templates/settings/two_factor.html apps/accounts/tests/test_two_factor_views.py
git commit -m "$(cat <<'EOF'
feat(settings): 2FA Disable/Regenerate route through confirm-password

PasswordConfirmationRequiredMixin now gates the two destructive 2FA
actions. Inline password inputs disappear from the 2FA tab template —
a single click on "Disable 2FA" or "Regenerate codes" detours through
/password/confirm/ (unless the user has a fresh 3-hour grace from a
prior confirm).

Phase 2 tests updated to reflect the new flow: there's no "wrong
password" path anymore at these endpoints, only "grace vs no grace".

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — E2E tests

**Files:**
- Create: `tests/e2e/test_auth_completion.py`

### Step 6.1 — Write the three tests

```python
import pyotp
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_register_and_verify_end_to_end(page, server_url, django_user_model):
    page.goto(f"{server_url}/accounts/register/")
    page.fill("#id_username", "newbie")
    page.fill("#id_email", "newbie@example.com")
    page.fill("#id_first_name", "New")
    page.fill("#id_last_name", "Bie")
    page.fill("#id_password1", "testpass-x9!")
    page.fill("#id_password2", "testpass-x9!")
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/email/verify/")
    assert page.locator("text=Check your email").is_visible()

    # Token isn't visible in the UI — compute from the DB and visit directly
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode
    user = django_user_model.objects.get(username="newbie")
    assert user.email_verified_at is None
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    page.goto(f"{server_url}/email/verify/{uidb64}/{token}/")
    page.wait_for_url(f"{server_url}/")
    user.refresh_from_db()
    assert user.email_verified_at is not None


def test_unverified_user_gated_from_orders(page, server_url, django_user_model):
    user = django_user_model.objects.create_user(
        username="alicee", email="alicee@example.com", password="pw-x9!", is_staff=False,
    )
    user.email_verified_at = None
    user.save()

    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", "alicee")
    page.fill("#id_password", "pw-x9!")
    page.click("button[type=submit]")
    # Without a protected-view redirect, login goes to /; the EmailVerifiedRequiredMixin
    # on DashboardView catches it and bounces to /email/verify/
    page.wait_for_url(f"{server_url}/email/verify/")
    # Try the orders URL directly — same gate
    page.goto(f"{server_url}/orders/")
    page.wait_for_url(f"{server_url}/email/verify/")


def test_confirm_password_gate_on_2fa_disable(page, server_url, django_user_model):
    from apps.accounts.two_factor import TwoFactorDevice
    from django.utils import timezone

    user = django_user_model.objects.create_user(
        username="bob", email="bob@example.com", password="pw-x9!", is_staff=False,
    )
    user.email_verified_at = timezone.now()
    user.save()
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    d.generate_recovery_codes()

    # Log in (2FA challenge happens first since 2FA is confirmed)
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", "bob")
    page.fill("#id_password", "pw-x9!")
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/accounts/two-factor/")
    page.fill('input[name="code"]', pyotp.TOTP(d.secret).now())
    page.click('button:has-text("Verify")')
    page.wait_for_url(f"{server_url}/")

    # Click Disable on the 2FA settings page → detours through confirm-password
    page.goto(f"{server_url}/settings/two-factor/")
    page.click('button:has-text("Disable 2FA")')
    page.wait_for_url(lambda url: url.startswith(f"{server_url}/password/confirm/"))
    page.fill('input[name="password"]', "pw-x9!")
    page.click('button:has-text("Confirm password")')
    page.wait_for_url(f"{server_url}/settings/two-factor/")
    # 2FA should be disabled now
    assert not TwoFactorDevice.objects.filter(user=user).exists()
```

### Step 6.2 — Run the E2E tests

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/test_auth_completion.py -m e2e -v 2>&1 | tail -20`
Expected: 3 passed.

If the first test fails because `/accounts/register/` has different field IDs than listed, inspect `templates/accounts/register.html` and fix the fills. Django's default for RegisterForm renders fields with `id="id_<fieldname>"` — should match as written.

If the 2FA test fails because the login redirect doesn't go to `/accounts/two-factor/`, the session might lose `pre_2fa_user_id` — rerun once; it's usually a timing issue with Alpine hydration. The shell tests already use a `wait_for_function` helper; copy that pattern in if needed.

### Step 6.3 — Full regression

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -q 2>&1 | tail -3`
Expected: 167 passed.

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/ -m e2e -q 2>&1 | tail -3`
Expected: 13 passed (10 prior + 3 new).

### Step 6.4 — Commit

```bash
git add tests/e2e/test_auth_completion.py
git commit -m "$(cat <<'EOF'
test(e2e): verify-email flow + unverified gate + confirm-password gate

Three Playwright tests covering the Phase 3 surface end-to-end:
- Register new user → lands on verify page → visit confirmed
  token URL → dashboard loads, email_verified_at is set
- Unverified user login: redirected to /email/verify/ from both
  dashboard and orders
- 2FA Disable on a live account: click Disable → detoured to
  /password/confirm/ → enter password → 2FA actually disabled

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Done — Phase 3 complete

Summary:
- 6 commits on `phase3-auth-completion` branch
- Verify-email flow: prompt / confirm / resend / console email backend
- Email uniqueness + `email_verified_at` field + dev email delivery
- `EmailVerifiedRequiredMixin` gate on every protected CBV
- `PasswordConfirmationRequiredMixin` + `ConfirmPasswordView` (sudo mode)
- 2FA Disable / Regenerate now route through confirm-password (no more inline password inputs)
- +~29 unit tests, +3 E2E tests (total: 167 unit + 13 E2E)
- No new deps

After Task 6 passes, hand off to `finishing-a-development-branch` for merge to main.

Next up: Phase 4 — Missing CRUD modules (customers, invoices, roles). Separate brainstorm + spec + plan.
