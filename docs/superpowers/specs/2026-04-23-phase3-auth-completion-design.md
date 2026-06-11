# Phase 3 — Auth Completion

**Date:** 2026-04-23
**Status:** Approved (brainstorming)
**Scope:** Third of the 7-phase port. Closes the auth gaps in the v0.1.0 README: verify-email flow (including console email backend, `email_verified_at` field, and email uniqueness) plus confirm-password "sudo mode" middleware applied to the 2FA disable/regenerate actions.

## Context

Phase 1 shipped the shell; Phase 2 added the 4 settings tabs plus full TOTP 2FA (including the login challenge, which was pulled forward from Phase 3's original scope). What remains from the reference Apex auth surface:

- **verify-email** — today `RegisterView` auto-logs-in without verification (documented as a known limitation in v0.1.0)
- **confirm-password** — reference uses it as middleware protecting sensitive actions; we'll apply it to `TwoFactorDisableView` / `TwoFactorRegenerateView` (replacing their inline password field)

Plus two pieces of infrastructure that the verify-email flow forces us to fix:

- `User.email` is not unique (TODO left in `models.py`)
- No `EMAIL_BACKEND` configured — password-reset emails silently fail in dev because Django falls back to SMTP

## Goals

Close the two reference-parity auth pages (verify-email + confirm-password) and wire them into the existing app such that:

- New registrations require email verification before accessing protected views
- Existing 2FA disable/regenerate use the confirm-password detour instead of an inline password input
- Password-reset emails work in dev (console backend)

## Non-goals

- OAuth / social login
- Magic-link login (passwordless email auth)
- Rate limiting beyond the 60-second resend cooldown (broader rate-limit is a Phase 2 follow-up ticket)
- Email change flow on the profile page protected by confirm-password (profile form stays as-is; changing email is still inline with the other fields)
- Delete-account flow (not in scope; would be a natural consumer of confirm-password later)

## Features

| Feature | Behaviour |
|---|---|
| **Verify-email** | After registration: auto-login, send verification email, redirect to `/email/verify/`. Unverified users get redirected to the prompt page on every protected view via `EmailVerifiedRequiredMixin`. Clicking the link in the email (or visiting `/email/verify/<uidb64>/<token>/`) sets `email_verified_at` and redirects to `/`. Already-verified link is idempotent (short-circuits with success). Resend is rate-gated to 60 sec per session. |
| **Confirm-password** | Views decorated with `PasswordConfirmationRequiredMixin` redirect unsatisfied users to `/password/confirm/?next=<path>`. POST with correct password sets `session.password_confirmed_at = now()` and redirects to `next` (with a safe-redirect guard). Grace window: 3 hours. |
| **2FA rewiring** | `TwoFactorDisableView` and `TwoFactorRegenerateView` gain `PasswordConfirmationRequiredMixin`; drop their inline password inputs from the template. First destructive action prompts for password; follow-ups within 3 hours don't. |
| **Email infrastructure** | `User.email` gains `unique=True`; case-insensitive via lowercased storage in `save()`. New `email_verified_at` timestamp (nullable; `None` means unverified). Console backend in dev; prod unchanged. Demo + factory users seeded as verified so dev workflow isn't interrupted. |

## Architecture

### URLs

```
apex/urls.py  (auth area — new routes)
  /email/verify/                    → EmailVerifyPromptView           (name="email_verify_prompt")
  /email/verify/<uidb64>/<token>/   → EmailVerifyConfirmView         (name="email_verify_confirm")
  /email/verify/resend/             → EmailVerifyResendView          (name="email_verify_resend")
  /password/confirm/                → ConfirmPasswordView            (name="confirm_password")
```

No changes to existing auth routes (`/accounts/login/`, `/accounts/logout/`, password-reset chain, 2FA challenge) or to `settings_urls.py`.

### Views

- `EmailVerifyPromptView(LoginRequiredMixin, TemplateView)` — renders "check your email" page. Exempt from `EmailVerifiedRequiredMixin` so unverified users can reach it.
- `EmailVerifyConfirmView(View)` — GET. Validates `uidb64` + token via Django's `default_token_generator`. On success sets `email_verified_at`, logs user in if anonymous, redirects to `/`. Bad token renders `email_verify_invalid.html`. Idempotent if already verified.
- `EmailVerifyResendView(LoginRequiredMixin, View)` — POST. 60-second cooldown via `session["verify_email_sent_at"]`. Re-sends email. Exempt from `EmailVerifiedRequiredMixin`.
- `ConfirmPasswordView(LoginRequiredMixin, View)` — GET renders form. POST validates password against current user; on success writes `session["password_confirmed_at"] = now()` and redirects to `?next=` (safe-redirect checked).

### Mixins

- `EmailVerifiedRequiredMixin` — redirects unverified users to `email_verify_prompt`. Exempt list (views that do NOT mix it in): `RegisterView`, all three `EmailVerify*View` classes, `LoginView`, `LogoutView`, all password-reset views, `ConfirmPasswordView`, `TwoFactorChallengeView`. Every other protected CBV gets it.
- `PasswordConfirmationRequiredMixin` — grace 3 hours. MRO: place AFTER `LoginRequiredMixin` so unauthenticated users redirect to login, not to a confirm page they can't reach.

### Middleware approach — rejected

Considered verifying-email as middleware. Rejected for:

- Mixin is Django-idiomatic and matches our existing `LoginRequiredMixin` / `BreadcrumbsMixin` pattern
- Middleware risks silent skips on unexpected surfaces (register, password-reset, logout)
- Explicit opt-out list is auditable

### Model changes

```python
# apps/accounts/models.py
class User(AbstractUser):
    email = models.EmailField(unique=True)                            # override AbstractUser
    email_verified_at = models.DateTimeField(null=True, blank=True)   # new
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default="staff")
    bio = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)
```

### Settings

```python
# apex/settings/dev.py
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "Apex Dashboard <noreply@apex.local>"
```

Prod settings unchanged (prod deployment handles SMTP via env vars outside the scope of this branch).

### Dependencies

None. Uses Django's built-ins:
- `django.contrib.auth.tokens.default_token_generator`
- `django.utils.http.urlsafe_base64_encode` / `urlsafe_base64_decode`
- `django.utils.encoding.force_bytes`
- `django.core.mail.send_mail`
- `django.utils.http.url_has_allowed_host_and_scheme`

## Data model

### Migration

`apps/accounts/migrations/000N_email_verification.py` — two schema operations wrapped around a `RunPython` backfill:

```python
def backfill_emails(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    seen = set()
    for u in User.objects.order_by("pk"):
        email = (u.email or "").strip().lower()
        if not email:
            email = f"{u.username}@apex.local"
        if email in seen:
            email = f"{u.username}+{u.pk}@apex.local"
        u.email = email
        seen.add(email)
        if not u.email_verified_at:
            u.email_verified_at = timezone.now()
        u.save(update_fields=["email", "email_verified_at"])


operations = [
    migrations.AddField("User", "email_verified_at",
                        models.DateTimeField(null=True, blank=True)),
    migrations.RunPython(backfill_emails, migrations.RunPython.noop),
    migrations.AlterField("User", "email",
                          models.EmailField(max_length=254, unique=True)),
]
```

Ordering matters: `email_verified_at` added first (nullable, no default), backfill runs, THEN `email` uniqueness is enforced. Partial migration failure leaves the table in a known state.

### Demo data

`apps/core/management/commands/seed_demo.py` — set `email_verified_at = timezone.now()` on demo user and each factory-generated user; give each factory user a unique `+<n>` suffix in their email so uniqueness holds.

## Flows

### Flow A — Verify-email

```
POST /accounts/register/  (RegisterView.post)
  → create User (email_verified_at=None)
  → auth_login(user)
  → send_verify_email(user, request)
  → redirect to /email/verify/

GET /email/verify/  (EmailVerifyPromptView)
  → if user.email_verified_at is not None: redirect to "/"
  → render prompt with resend button + sign-out
  → if session.verify_email_sent_at fresh: show "new link sent" flash

POST /email/verify/resend/  (EmailVerifyResendView)
  → cooldown check: session.verify_email_sent_at within 60s → flash cooldown
  → else send_verify_email(user, request); session.verify_email_sent_at = now()
  → redirect to /email/verify/

GET /email/verify/<uidb64>/<token>/  (EmailVerifyConfirmView)
  → decode uidb64 → uid
  → user = User.objects.filter(pk=uid).first()  ; None → invalid page
  → if user.email_verified_at is not None: success flash, redirect "/"   (idempotent)
  → if default_token_generator.check_token(user, token):
       user.email_verified_at = now(); user.save()
       if anon: auth_login(request, user)
       messages.success("Email verified")
       redirect "/"
     else:
       render email_verify_invalid.html
```

### Flow B — Confirm-password

```
GET /any/sensitive/view/
  → PasswordConfirmationRequiredMixin.dispatch:
       stamp = session.get("password_confirmed_at")
       if not stamp or now - stamp > 3h:
           redirect("/password/confirm/?next=/any/sensitive/view/")
       else:
           proceed

GET /password/confirm/
  → render form with `next` as hidden input

POST /password/confirm/
  → authenticate(username, password)
  → on success:
       session["password_confirmed_at"] = now().isoformat()
       next_url = cleaned next from POST (url_has_allowed_host_and_scheme)
       redirect(next_url or "/")
  → on failure: re-render with inline error
```

### Flow C — 2FA rewiring

```
Before (Phase 2):
  POST /settings/two-factor/disable/ with password → verify → delete device

After (Phase 3):
  POST /settings/two-factor/disable/  (no form payload beyond CSRF)
    → PasswordConfirmationRequiredMixin.dispatch:
         if confirmed within 3h: proceed
         else: redirect to /password/confirm/?next=/settings/two-factor/disable/
    → delete device
    → redirect "/settings/two-factor/" with success message
```

Same transformation for `TwoFactorRegenerateView`. Templates lose their inline `<input type="password">` fields.

## Error handling

- **Token decode failure**: `force_str(urlsafe_base64_decode(uidb64))` raises on malformed input; caught and renders invalid page.
- **User deleted between email-send and click**: `User.objects.filter(pk=uid).first()` returns None; invalid page.
- **Resend abuse within cooldown**: cooldown flash; session flag prevents the send. No DB write. No per-IP rate limit (out of scope).
- **`next=` open-redirect**: `url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})` — any off-host URL falls back to "/".
- **Seeded users with dup emails mid-migration**: `RunPython` backfill dedupes before `unique=True` is applied.
- **Email send failure in prod**: `send_mail` raises; surface via default exception handling (500 page). In dev, console backend can't fail. Retry is not in scope.
- **Password-confirmation session tampering**: if user sets `password_confirmed_at` to a bogus value, `datetime.fromisoformat` raises; caught and treated as unconfirmed.

## Testing

### Unit (pytest) — ~18 new tests

**`test_verify_email.py`** (~11):
- Register POST creates user with `email_verified_at=None`
- Register POST sends a verification email (`mail.outbox` populated, contains verify URL)
- Register POST redirects to `/email/verify/`
- Unverified user hitting `/` / `/orders/` / `/settings/profile/` redirects to `/email/verify/`
- `EmailVerifyConfirmView` with valid `uidb64+token` sets `email_verified_at`, redirects to `/`
- Confirm view with bad `uidb64` → invalid page
- Confirm view with tampered token → invalid page, email stays unverified
- Already-verified user clicking their link → idempotent success
- Resend sends a new email
- Resend within 60s → cooldown, no new email
- Exempt views (verify prompt, logout) remain accessible for unverified users

**`test_confirm_password.py`** (~5):
- Access PCRM-protected view without grace → redirects to `/password/confirm/?next=...`
- Correct password sets session grace + redirects to `next`
- Wrong password stays on confirm page with error
- Grace older than 3 hours → re-challenged
- Malicious `next=https://evil.example.com/` → falls back to "/"

**`test_user_model.py`** (~2):
- Duplicate email at form save raises validation
- Case-insensitive uniqueness (`Alice@X.com` vs `alice@x.com`)

### E2E (Playwright) — 3 new tests

- **Register + verify**: register new user via UI → lands on verify page → pull token from DB helper → visit confirm URL → dashboard visible with success message
- **Unverified gate**: register new user → attempt `/orders/` → redirected to `/email/verify/`
- **Confirm-password gate on 2FA disable**: pre-seed user with confirmed 2FA → login → clear session `password_confirmed_at` → click "Disable 2FA" → redirected to `/password/confirm/` → enter password → back to 2FA page → 2FA disabled

## Rollout — 6 commits

1. **Email infra** — console backend, `email_verified_at` field, email uniqueness, migration with backfill, seed demo auto-verified
2. **Verify-email views + templates** — all three views, email templates (txt + html), prompt + invalid pages, `RegisterView` plumbing, resend cooldown
3. **`EmailVerifiedRequiredMixin` + sweep** — mixin in `apps/accounts/mixins.py`, applied to every non-exempt CBV
4. **Confirm-password infrastructure** — `PasswordConfirmationRequiredMixin`, `ConfirmPasswordView`, template, safe-redirect guard
5. **2FA rewiring** — swap Disable + Regenerate views to use PCRM; drop inline password inputs from `templates/settings/two_factor.html`; update Phase 2 tests that posted `password=`
6. **E2E tests** — 3 Playwright tests

## Open questions

None. User approved all 4 design sections and confirmed the Full-parity scope.

## Known follow-ups not in Phase 3

- Per-IP / per-user rate limit for resend + confirm-password (still a Phase 2 follow-up)
- Delete-account flow (natural consumer of confirm-password when it lands)
- Email-change detection on the profile form (could prompt for confirm-password only when `email` actually changes)
