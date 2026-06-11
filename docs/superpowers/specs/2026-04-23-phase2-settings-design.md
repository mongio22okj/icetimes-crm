# Phase 2 — Settings Expansion

**Date:** 2026-04-23
**Status:** Approved (brainstorming)
**Scope:** Second of the 7-phase port of the Apex Next.js/Laravel dashboard to Django-native. Splits the one-page settings into 4 tabs (Profile, Password, Appearance, Two-factor) and ships 2FA as a complete feature including the login challenge.

## Context

Phase 1 shipped the shell (palette, drawer, dropdown, breadcrumbs). The current `/settings/` page is a single `ProfileView` form — it combines name/email/bio/avatar. The reference Apex dashboard has four independent settings tabs behind a left-rail nav. Phase 2 closes that gap.

Decision recorded during brainstorming: **ship 2FA whole** (settings tab + login challenge) rather than deferring the challenge to Phase 3. Enabling 2FA must actually enforce 2FA at login. Phase 3 retains verify-email and confirm-password; it no longer owns 2FA.

## Goals

Reference-parity for the four settings tabs, plus a working TOTP + recovery-code 2FA flow enforced at login.

## Non-goals

- Encrypted-at-rest storage of the TOTP secret (standard practice for Django 2FA libraries is plaintext-in-DB; field-level encryption is a future concern).
- WebAuthn / FIDO2 / push-based 2FA — TOTP only.
- Per-user theme persistence to the database — localStorage only.
- Audit trail of recovery-code usage beyond a `used_at` timestamp on each code.
- Delete-account flow (reference has it on the Profile tab; not in scope here).

## Features

| Tab | Contents |
|---|---|
| **Profile** | Existing name/email/bio/avatar form, moved into the tabs layout |
| **Password** | Change password while logged in. Uses Django's `PasswordChangeForm`; calls `update_session_auth_hash` so the user stays authenticated. |
| **Appearance** | Light / Dark / System picker. localStorage only; no DB write. "System" removes the saved key and falls back to `prefers-color-scheme`. |
| **Two-factor** | Enable (password-confirmed) → QR scan + TOTP verify → recovery codes displayed once. Disable (password-confirmed). Regenerate recovery codes (password-confirmed). |

Plus a cross-cutting **login challenge**: after successful password authentication, if the user has a confirmed 2FA device, the login flow redirects to a TOTP entry step before session login completes.

## Architecture

### URLs

```
apex/urls.py
  /accounts/login/            → TwoFactorAwareLoginView    (replaces auth_views.LoginView)
  /accounts/two-factor/       → TwoFactorChallengeView     (NEW, name="two_factor_challenge")
  /settings/                  → include settings_urls.py

apps/accounts/settings_urls.py   (renamed from profile_urls.py; app_name = "settings")
  ""                          → redirect to settings:profile
  "profile/"                  → ProfileView                (name="profile")
  "password/"                 → PasswordChangeView         (name="password")
  "appearance/"               → AppearanceView             (name="appearance")
  "two-factor/"               → TwoFactorView              (name="two_factor")
  "two-factor/enable/"        → TwoFactorEnableView        (name="two_factor_enable")
  "two-factor/setup/"         → TwoFactorSetupView         (name="two_factor_setup")
  "two-factor/disable/"       → TwoFactorDisableView       (name="two_factor_disable")
  "two-factor/regenerate/"    → TwoFactorRegenerateView    (name="two_factor_regenerate")
```

Phase 1's `NAV_ITEMS` Settings entry flips its `url_name` from `profile:edit` to `settings:profile`.

### Templates

```
templates/
  layouts/
    settings.html                 NEW  extends layouts/dashboard.html
                                       renders the left-rail tab nav + {% block settings_content %}
  accounts/
    profile.html                  MODIFY  now extends layouts/settings.html
  settings/                       NEW directory
    password.html
    appearance.html
    two_factor.html
    two_factor_setup.html
    _recovery_codes_panel.html
  registration/
    two_factor_challenge.html     NEW  extends layouts/auth.html
```

### Views

- `ProfileView` — existing; only the template path changes (already extends settings layout via the partial update).
- `PasswordChangeView(BreadcrumbsMixin, LoginRequiredMixin, FormView)` — uses Django's `PasswordChangeForm`; calls `update_session_auth_hash` in `form_valid`.
- `AppearanceView(BreadcrumbsMixin, LoginRequiredMixin, TemplateView)` — template-only, no form.
- `TwoFactorView(BreadcrumbsMixin, LoginRequiredMixin, TemplateView)` — reads user's 2FA state, renders the appropriate panel (off / unconfirmed / active).
- `TwoFactorEnableView(LoginRequiredMixin, View)` — POST-only. Validates password, creates unconfirmed `TwoFactorDevice` (deleting any existing one), redirects to setup.
- `TwoFactorSetupView(LoginRequiredMixin, View)` — GET shows QR + manual key + TOTP input. POST verifies code, marks confirmed, generates 8 recovery codes, flashes plaintext codes via `messages`, redirects to `settings:two_factor`.
- `TwoFactorDisableView(LoginRequiredMixin, View)` — POST-only. Requires password; deletes device.
- `TwoFactorRegenerateView(LoginRequiredMixin, View)` — POST-only. Requires password; replaces recovery codes.
- `TwoFactorAwareLoginView(auth_views.LoginView)` — subclass; overrides `form_valid` to stash user id in session and redirect to challenge when user has a confirmed device. Falls back to standard login for non-2FA users.
- `TwoFactorChallengeView(View)` — GET renders TOTP input. POST accepts TOTP or recovery code; on success, completes `login()` and redirects to the original `next` URL.

### Forms

- `PasswordChangeForm` — Django built-in; we apply BASE_INPUT classes in `__init__`.
- `TwoFactorSetupForm` — single `code` field (6 digits, IntegerField with custom validation).
- `TwoFactorDisableForm` — single `password` field.
- `TwoFactorChallengeForm` — single `code` field accepting either a 6-digit TOTP or a "XXXXX-XXXXX" recovery code.

### Dependencies

Added to `pyproject.toml`:
- `pyotp ~= 2.9` — TOTP generation + verification, pure Python
- `qrcode ~= 7.4` — SVG QR rendering, no PIL/Pillow dependency

Both small, pure-Python, well-maintained.

## Data model

```python
# apps/accounts/models.py

class TwoFactorDevice(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="two_factor",
    )
    secret = models.CharField(max_length=32)
    confirmed = models.BooleanField(default=False)
    recovery_codes = models.JSONField(default=list)
    # Shape: [{"hash": "<sha256-hex>", "used_at": null|ISO-8601-string}, ...]
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def provisioning_uri(self) -> str: ...
    def verify_totp(self, code: str, valid_window: int = 1) -> bool: ...
    def verify_recovery_code(self, code: str) -> bool: ...
    def generate_recovery_codes(self, count: int = 8) -> list[str]: ...

    @staticmethod
    def create_unconfirmed(user) -> "TwoFactorDevice": ...
```

Module-level helpers:
- `_random_recovery_code()` — returns `"XXXXX-XXXXX"` using an ambiguity-free alphabet (excludes O, 0, I, 1).
- `_hash_recovery_code(code)` — sha256 hex digest.

**One-table design (recovery codes as JSON)** is chosen over a separate `RecoveryCode` table:

- Always ≤ 8-10 rows per user
- No cross-user queries ever
- Atomic "mark used" is a single row update
- Schema surface minimized; migration trivial

### Migration

One forward migration creating `TwoFactorDevice` with a `OneToOneField` to `User`.

## Flows

### Flow A — 2FA setup

```
/settings/two-factor/  (TwoFactorView)
  → renders one of three panels based on device state:
     * no device        → "Enable 2FA" form (password + submit)
     * unconfirmed dev  → "Finish setup" link
     * confirmed dev    → Active status + recovery codes + Disable form

POST /settings/two-factor/enable/  (TwoFactorEnableView)
  → require password
  → TwoFactorDevice.create_unconfirmed(user)   (deletes existing device first)
  → redirect to /settings/two-factor/setup/

GET /settings/two-factor/setup/  (TwoFactorSetupView)
  → require an unconfirmed device; otherwise redirect to /settings/two-factor/
  → render QR (inline SVG from qrcode lib) + manual key + TOTP input + Cancel button

POST /settings/two-factor/setup/  (same view)
  → verify_totp(code)
  → on success:
       device.confirmed = True
       device.confirmed_at = now()
       codes = device.generate_recovery_codes(8)
       messages.success(request, codes)  (tagged with "recovery_codes")
       redirect to /settings/two-factor/
  → on failure: re-render with inline error
```

### Flow B — Disable / regenerate

```
POST /settings/two-factor/disable/
  → require password
  → delete the TwoFactorDevice row
  → flash "2FA disabled"
  → redirect to /settings/two-factor/

POST /settings/two-factor/regenerate/
  → require password
  → new_codes = device.generate_recovery_codes(8)
  → flash codes via messages.success with "recovery_codes" tag
  → redirect to /settings/two-factor/
```

### Flow C — Login challenge

```
POST /accounts/login/  (TwoFactorAwareLoginView.form_valid)
  → password validated (super call semantics)
  → if user has confirmed TwoFactorDevice:
       session["pre_2fa_user_id"] = user.pk
       session["pre_2fa_next"] = self.get_success_url()
       redirect to /accounts/two-factor/
  → else: normal login (super().form_valid)

GET /accounts/two-factor/
  → require session["pre_2fa_user_id"]; else redirect to login
  → render TOTP entry form + "Use a recovery code instead" disclosure

POST /accounts/two-factor/
  → require session["pre_2fa_user_id"]
  → fetch user; verify_totp(code) OR verify_recovery_code(code)
  → on success:
       next_url = session.pop("pre_2fa_next") or LOGIN_REDIRECT_URL
       session.pop("pre_2fa_user_id")
       user.backend = "django.contrib.auth.backends.ModelBackend"
       login(request, user)
       redirect(next_url)
  → on failure: re-render with error "Invalid code. Try again or use a recovery code."
```

## Error handling

- **TOTP replay within window**: `pyotp.verify(..., valid_window=1)` is fine for 2FA UX; replay attacks against a single 30-sec window require simultaneous session control and are out of the Phase 2 threat model.
- **Setup without unconfirmed device**: the setup GET redirects to `/settings/two-factor/` if the user has no device-in-progress, preventing error states when a user bookmarks `/setup/`.
- **Challenge without session key**: GET and POST both redirect to `/accounts/login/` if the session lacks `pre_2fa_user_id`, preventing stale-state logins.
- **Recovery code double-use**: `verify_recovery_code` marks the code used on first success and returns False on subsequent attempts.
- **Password-change session drop**: `update_session_auth_hash` is called so changing your password doesn't immediately log you out.
- **Appearance localStorage access blocked** (private browsing, strict settings): the picker simply doesn't persist — no failure state to show.

## Testing

### Unit (pytest) — ~15 new tests

- `TwoFactorDevice.provisioning_uri` yields valid `otpauth://totp/...` with issuer
- `verify_totp` accepts the current window's code
- `verify_totp` rejects wrong code
- `verify_recovery_code` accepts on first call, rejects on second
- `verify_recovery_code` rejects invalid code without mutation
- `generate_recovery_codes` returns 8 plaintext codes, stores 8 hashes, used_at all null
- `create_unconfirmed` deletes any existing device before creating a new one
- `TwoFactorEnableView` requires password
- `TwoFactorSetupView` POST with wrong code → form has error, device not confirmed
- `TwoFactorSetupView` POST with right code → device confirmed, codes generated, flash set
- `TwoFactorDisableView` POST requires password; deletes device
- `TwoFactorAwareLoginView` redirects to challenge when user has confirmed device
- `TwoFactorAwareLoginView` delegates to super when user has no device
- `TwoFactorChallengeView` POST with valid TOTP completes login and redirects to `next`
- `TwoFactorChallengeView` POST with valid recovery code completes login and marks used
- `TwoFactorChallengeView` GET without session key redirects to login
- `PasswordChangeView` on success keeps the user logged in (via `update_session_auth_hash`)
- `AppearanceView` renders the picker

### E2E (Playwright) — 4 new tests

- Settings tabs navigation: each tab link navigates, active state shows in left-rail
- Enable 2FA: click enable, QR renders, type verified code, recovery codes appear
- 2FA-aware login: enable 2FA, log out, log in, challenge page shown, TOTP accepted, dashboard loads
- Appearance picker: click "Dark" → `document.documentElement.classList.contains('dark')` true and localStorage.theme == "dark"

## Rollout — 6 commits

1. **Tabs framework** — rename `profile_urls.py` → `settings_urls.py` (namespace → "settings"), update `NAV_ITEMS` to `settings:profile`, new `layouts/settings.html`, move Profile template into tabs. No behavioural change for the Profile form; 404-safe URL redirect from `/settings/` → `/settings/profile/`.
2. **Password tab** — `PasswordChangeView`, `templates/settings/password.html`, BASE_INPUT styled form, unit tests.
3. **Appearance tab** — `AppearanceView`, `templates/settings/appearance.html`, Alpine picker writing localStorage, unit test.
4. **2FA settings tab** — `TwoFactorDevice` model + migration, enable/setup/disable/regenerate views, templates, recovery codes partial, unit tests. Add `pyotp` + `qrcode` deps.
5. **2FA login challenge** — `TwoFactorAwareLoginView` + `TwoFactorChallengeView` + URL swap in `apex/urls.py` + `two_factor_challenge.html` template + unit tests.
6. **E2E tests** — 4 Playwright tests.

## Open questions

None. User approved all 4 design sections and both sub-choices (custom 2FA, localStorage appearance).

## Known limitations (filed as Phase 2 follow-ups)

- **TOTP attempt cap is session-scoped, not rate-limited.** `TwoFactorChallengeView` enforces 5 failed attempts per challenge session, but an attacker who has the password can clear cookies, re-auth, and restart the counter. For real rate-limiting, wire `django-ratelimit` (or a cache-based counter) keyed by `(user_id, minute-bucket)`. The current cap is UX-level only — good enough for a template dashboard, not sufficient for high-stakes production.
- **TOTP secret stored plaintext in DB.** Standard practice for Django 2FA libraries; field-level encryption (`django-cryptography` or similar) is a future-hardening item.
- **No audit log of 2FA events.** Enable / disable / regenerate / challenge-failure events are invisible. Add a `TwoFactorAuditEvent` model if this is deployed to real users.
- **Recovery-code input is hash-literal.** A user who types `ABCDEFGHIJ` instead of `ABCDE-FGHIJ` gets "Invalid code" — we don't normalize the input before hashing. Easy follow-up: `_hash_recovery_code` should strip non-alphanumeric chars and casefold before hashing.
