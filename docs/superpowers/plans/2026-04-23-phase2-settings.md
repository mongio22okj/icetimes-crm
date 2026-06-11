# Phase 2 — Settings Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the one-page settings with a tabbed interface (Profile, Password, Appearance, Two-factor) and ship 2FA as a complete feature including the post-password login challenge.

**Architecture:** Tabs live in a new `layouts/settings.html` that extends the existing dashboard layout with a left-rail nav and a content block. URL namespace migrates from `profile:` to `settings:`. 2FA uses a custom `TwoFactorDevice` model with `pyotp` + `qrcode` — no framework library. Login challenge is a thin `TwoFactorAwareLoginView` subclass that redirects confirmed-2FA users to a separate challenge view before `login()` completes.

**Tech Stack:** Django 5.1 · Tailwind v4 · Alpine.js 3.14 · pyotp 2.9 · qrcode 7.4 · pytest · Playwright.

**Reference spec:** [`docs/superpowers/specs/2026-04-23-phase2-settings-design.md`](../specs/2026-04-23-phase2-settings-design.md)

**6 commits:**
1. Tabs framework + URL namespace migration
2. Password tab
3. Appearance tab
4. 2FA settings tab (model, views, templates, deps)
5. 2FA login challenge
6. E2E tests

---

## Pre-flight

- [ ] **Confirm baseline: 101 unit tests pass and shell E2E is green before any edits.**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: `101 passed`.

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/test_shell.py -m e2e -q 2>&1 | tail -3`
Expected: `6 passed`.

- [ ] **Create and check out a feature branch.**

Run: `git switch -c phase2-settings`
Expected: `Switched to a new branch 'phase2-settings'`.

---

## Task 1 — Tabs framework + URL namespace migration

**Files:**
- Rename: `apps/accounts/profile_urls.py` → `apps/accounts/settings_urls.py`
- Modify: `apex/urls.py` (include path + name)
- Modify: `apps/core/navigation.py` (one string in NAV_ITEMS)
- Modify: `apps/accounts/views.py` (`ProfileView.success_url`)
- Create: `templates/layouts/settings.html`
- Modify: `templates/accounts/profile.html` (extends settings layout)
- Modify: `apps/accounts/tests/test_profile.py` (update URL path if needed)

### Step 1.1 — Rename the URL module and expand the routes

```bash
git mv apps/accounts/profile_urls.py apps/accounts/settings_urls.py
```

Then rewrite `apps/accounts/settings_urls.py`:

```python
from django.urls import path
from django.views.generic import RedirectView

from .views import ProfileView

app_name = "settings"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="settings:profile", permanent=False)),
    path("profile/", ProfileView.as_view(), name="profile"),
    # Password, appearance, two-factor routes added in Tasks 2–5.
]
```

### Step 1.2 — Update `apex/urls.py`

Find:
```python
    path("settings/", include("apps.accounts.profile_urls")),
```

Replace with:
```python
    path("settings/", include("apps.accounts.settings_urls")),
```

### Step 1.3 — Update `NAV_ITEMS` in `apps/core/navigation.py`

Change the Settings `NavItem`'s `url_name` from `"profile:edit"` to `"settings:profile"`. Only the single string changes.

### Step 1.4 — Update `ProfileView.success_url`

In `apps/accounts/views.py`, find:
```python
    success_url = reverse_lazy("profile:edit")
```
Replace with:
```python
    success_url = reverse_lazy("settings:profile")
```

### Step 1.5 — Create `templates/layouts/settings.html`

```html
{% extends "layouts/dashboard.html" %}
{% load apex %}
{% block title %}Settings · Apex{% endblock %}
{% block content %}
<div class="max-w-5xl">
  <h1 class="text-2xl font-bold tracking-tight mb-1">Settings</h1>
  <p class="text-sm text-muted-foreground mb-6">Manage your profile and account.</p>

  <div class="flex flex-col lg:flex-row gap-8">
    <aside class="w-full lg:w-48 shrink-0">
      <nav aria-label="Settings" class="flex flex-col gap-1">
        {% with path=request.path %}
          <a href="{% url 'settings:profile' %}"
             class="px-3 py-2 rounded-md text-sm hover:bg-accent hover:text-accent-foreground {% if path|slice:':19' == '/settings/profile/' or path == '/settings/profile' %}bg-accent text-accent-foreground font-medium{% endif %}">Profile</a>
          <a href="{% url 'settings:password' %}"
             class="px-3 py-2 rounded-md text-sm hover:bg-accent hover:text-accent-foreground {% if path|slice:':20' == '/settings/password/' or path == '/settings/password' %}bg-accent text-accent-foreground font-medium{% endif %}">Password</a>
          <a href="{% url 'settings:appearance' %}"
             class="px-3 py-2 rounded-md text-sm hover:bg-accent hover:text-accent-foreground {% if path|slice:':22' == '/settings/appearance/' or path == '/settings/appearance' %}bg-accent text-accent-foreground font-medium{% endif %}">Appearance</a>
          <a href="{% url 'settings:two_factor' %}"
             class="px-3 py-2 rounded-md text-sm hover:bg-accent hover:text-accent-foreground {% if path|slice:':22' == '/settings/two-factor' %}bg-accent text-accent-foreground font-medium{% endif %}">Two-factor</a>
        {% endwith %}
      </nav>
    </aside>
    <div class="flex-1 min-w-0">
      {% block settings_content %}{% endblock %}
    </div>
  </div>
</div>
{% endblock %}
```

**Note:** this layout calls `{% url 'settings:password' %}`, `{% url 'settings:appearance' %}`, `{% url 'settings:two_factor' %}` — routes that don't exist yet until Tasks 2/3/4. Rendering this layout BEFORE those routes exist will raise `NoReverseMatch`.

**Approach to avoid mid-plan breakage:** stub all four routes in `settings_urls.py` immediately (Step 1.6), pointing to a placeholder view. Later tasks replace each placeholder with the real view. This keeps the test suite green between tasks.

### Step 1.6 — Add placeholder URLs to `settings_urls.py`

Extend `apps/accounts/settings_urls.py` to:

```python
from django.urls import path
from django.views.generic import RedirectView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from .views import ProfileView


class _PlaceholderView(LoginRequiredMixin, TemplateView):
    """Temporary stub for Phase 2 tabs that land in later tasks."""
    template_name = "settings/_placeholder.html"


app_name = "settings"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="settings:profile", permanent=False)),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("password/", _PlaceholderView.as_view(), name="password"),
    path("appearance/", _PlaceholderView.as_view(), name="appearance"),
    path("two-factor/", _PlaceholderView.as_view(), name="two_factor"),
]
```

Create `templates/settings/_placeholder.html`:

```html
{% extends "layouts/settings.html" %}
{% block settings_content %}
<section class="rounded-lg border border-border bg-card p-6">
  <h2 class="text-base font-semibold">Coming soon</h2>
  <p class="text-sm text-muted-foreground mt-1">This settings tab lands in a follow-up task.</p>
</section>
{% endblock %}
```

### Step 1.7 — Move the Profile template into the tabs layout

Overwrite `templates/accounts/profile.html` — change only the `extends` and wrap the existing form in `{% block settings_content %}` instead of `{% block content %}`. Also drop the duplicate `<h1>Settings</h1>` header at the top because the layout already renders one.

Full replacement:

```html
{% extends "layouts/settings.html" %}
{% load apex %}

{% block settings_content %}
<div class="mb-6">
  <h2 class="text-lg font-semibold">Profile</h2>
  <p class="text-sm text-muted-foreground">Update your profile information.</p>
</div>

<form method="post" enctype="multipart/form-data" class="space-y-6">
  {% csrf_token %}
  {% if form.non_field_errors %}
    <div class="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{{ form.non_field_errors }}</div>
  {% endif %}

  <section class="rounded-lg border border-border bg-card p-6">
    <h3 class="text-base font-semibold">Profile photo</h3>
    <p class="text-sm text-muted-foreground mb-4">PNG or JPG, up to 2 MB.</p>
    <div class="flex items-center gap-4">
      {% if user.avatar %}
        <img src="{{ user.avatar.url }}" alt="" class="h-16 w-16 rounded-full object-cover" />
      {% else %}
        <span class="h-16 w-16 rounded-full inline-flex items-center justify-center text-lg font-semibold text-white"
              style="background-color: {{ user|avatar_color }};">{{ user|initials }}</span>
      {% endif %}
      <label class="inline-flex h-9 px-3 items-center rounded-md border border-input bg-background text-sm font-medium hover:bg-accent cursor-pointer">
        <span>Change photo</span>
        <span class="sr-only">Upload avatar</span>
        <span class="hidden">{{ form.avatar }}</span>
      </label>
    </div>
    {% if form.avatar.errors %}<p class="text-xs text-destructive mt-2">{{ form.avatar.errors.0 }}</p>{% endif %}
  </section>

  <section class="rounded-lg border border-border bg-card p-6 space-y-4">
    <div>
      <h3 class="text-base font-semibold">Account</h3>
      <p class="text-sm text-muted-foreground">Your username is <span class="font-mono">{{ user.username }}</span> (cannot be changed).</p>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label for="{{ form.first_name.id_for_label }}" class="block text-sm font-medium mb-1.5">First name</label>
        {{ form.first_name }}
        {% if form.first_name.errors %}<p class="text-xs text-destructive mt-1">{{ form.first_name.errors.0 }}</p>{% endif %}
      </div>
      <div>
        <label for="{{ form.last_name.id_for_label }}" class="block text-sm font-medium mb-1.5">Last name</label>
        {{ form.last_name }}
        {% if form.last_name.errors %}<p class="text-xs text-destructive mt-1">{{ form.last_name.errors.0 }}</p>{% endif %}
      </div>
    </div>
    <div>
      <label for="{{ form.email.id_for_label }}" class="block text-sm font-medium mb-1.5">Email address</label>
      {{ form.email }}
      {% if form.email.errors %}<p class="text-xs text-destructive mt-1">{{ form.email.errors.0 }}</p>{% endif %}
    </div>
    <div>
      <label for="{{ form.bio.id_for_label }}" class="block text-sm font-medium mb-1.5">Bio</label>
      {{ form.bio }}
      {% if form.bio.errors %}<p class="text-xs text-destructive mt-1">{{ form.bio.errors.0 }}</p>{% endif %}
    </div>
  </section>

  <div class="flex justify-end gap-2">
    <button type="submit" class="h-10 px-4 rounded-md bg-primary text-primary-foreground inline-flex items-center font-medium hover:opacity-90 transition-opacity">Save changes</button>
  </div>
</form>
{% endblock %}
```

### Step 1.8 — Update `test_profile.py` to target the new path

Open `apps/accounts/tests/test_profile.py`. Any assertion that does `client.get("/settings/")` for a logged-in user now gets a 302 redirect to `/settings/profile/`. Update those lines to either:
- hit `/settings/profile/` directly, OR
- call `client.get("/settings/", follow=True)` and assert on the final response.

Prefer the direct path:

```python
# Change occurrences of:
response = client.get("/settings/")
# to:
response = client.get("/settings/profile/")
```

The unauthenticated-redirect test at the top of the file stays on `/settings/` — an anon user just gets a login redirect regardless, so the test still passes.

### Step 1.9 — Run unit tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: `101 passed`.

If any test fails, investigate before adjusting the test.

### Step 1.10 — Rebuild Tailwind

Run: `npm run build 2>&1 | tail -2`
Expected: `Done in ...ms`.

### Step 1.11 — Smoke test

Start the dev server in the background if not running:
```
/Users/silkalns/.local/bin/uv run python manage.py runserver 127.0.0.1:8000 &
```

Log in and hit `/settings/`:
```
curl -s -c /tmp/t1.txt http://127.0.0.1:8000/accounts/login/ > /dev/null
TOKEN=$(awk '$6 == "csrftoken" { print $7 }' /tmp/t1.txt)
curl -s -b /tmp/t1.txt -c /tmp/t1.txt -H "Referer: http://127.0.0.1:8000/accounts/login/" \
  -d "username=demo&password=demo1234&csrfmiddlewaretoken=$TOKEN" \
  http://127.0.0.1:8000/accounts/login/ -o /dev/null
curl -s -b /tmp/t1.txt -o /dev/null -w '%{http_code} -> %{redirect_url}\n' http://127.0.0.1:8000/settings/
curl -s -b /tmp/t1.txt http://127.0.0.1:8000/settings/profile/ | grep -c 'Settings\|Profile photo\|Password\|Appearance\|Two-factor'
```
Expected:
- First line: `302 -> http://127.0.0.1:8000/settings/profile/`
- Second line: ≥ 4 (all 4 tab labels render in the left-rail plus "Profile photo" heading)

### Step 1.12 — Commit

```bash
git add apps/accounts/settings_urls.py apex/urls.py apps/core/navigation.py apps/accounts/views.py apps/accounts/tests/test_profile.py templates/layouts/settings.html templates/settings/_placeholder.html templates/accounts/profile.html
git rm --cached apps/accounts/profile_urls.py 2>/dev/null || true
git commit -m "$(cat <<'EOF'
feat(accounts): settings tabs framework (URL namespace + layout)

Moves /settings/ to a tabbed layout with left-rail nav. Renames the
URL namespace from `profile:` to `settings:` and updates NAV_ITEMS.
Profile tab is functional; Password/Appearance/Two-factor stub
placeholders land their real content in follow-up tasks.

/settings/ now redirects to /settings/profile/ so bookmarks still work.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — Password tab

**Files:**
- Modify: `apps/accounts/views.py` (new `PasswordChangeView`)
- Modify: `apps/accounts/settings_urls.py` (replace placeholder with real view)
- Modify: `apps/accounts/forms.py` (new `StyledPasswordChangeForm`)
- Create: `templates/settings/password.html`
- Create: `apps/accounts/tests/test_password_change.py`

### Step 2.1 — Add a styled form to `apps/accounts/forms.py`

At the bottom of the file, append:

```python
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm


class StyledPasswordChangeForm(DjangoPasswordChangeForm):
    """Django's PasswordChangeForm with BASE_INPUT classes applied."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", BASE_INPUT)
```

### Step 2.2 — Write the failing tests

Create `apps/accounts/tests/test_password_change.py`:

```python
import pytest
from django.urls import reverse
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_password_change_requires_login(client):
    response = client.get("/settings/password/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_password_change_renders_form_fields(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/settings/password/")
    assert response.status_code == 200
    assert b"Current password" in response.content
    assert b"New password" in response.content


def test_password_change_success_keeps_user_logged_in(client):
    user = UserFactory()
    user.set_password("oldpass1234")
    user.save()
    assert client.login(username=user.username, password="oldpass1234")

    response = client.post(
        "/settings/password/",
        {
            "old_password": "oldpass1234",
            "new_password1": "newpass-x9!",
            "new_password2": "newpass-x9!",
        },
        follow=True,
    )
    assert response.status_code == 200
    # Still authenticated (user stays logged in)
    assert response.context["user"].is_authenticated
    user.refresh_from_db()
    assert user.check_password("newpass-x9!")


def test_password_change_rejects_wrong_old_password(client):
    user = UserFactory()
    user.set_password("oldpass1234")
    user.save()
    client.login(username=user.username, password="oldpass1234")

    response = client.post(
        "/settings/password/",
        {
            "old_password": "WRONG",
            "new_password1": "newpass-x9!",
            "new_password2": "newpass-x9!",
        },
    )
    assert response.status_code == 200
    assert b"Your old password was entered incorrectly" in response.content
    user.refresh_from_db()
    assert user.check_password("oldpass1234"), "password should be unchanged"


def test_password_change_rejects_mismatched_confirmation(client):
    user = UserFactory()
    user.set_password("oldpass1234")
    user.save()
    client.login(username=user.username, password="oldpass1234")

    response = client.post(
        "/settings/password/",
        {
            "old_password": "oldpass1234",
            "new_password1": "newpass-x9!",
            "new_password2": "different",
        },
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("oldpass1234"), "password should be unchanged"
```

### Step 2.3 — Run tests to confirm they fail

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_password_change.py -v 2>&1 | tail -15`
Expected: 5 failures with `TemplateDoesNotExist` or `NoReverseMatch` (the placeholder renders a different page).

### Step 2.4 — Implement `PasswordChangeView` in `apps/accounts/views.py`

Add imports at the top (after the existing ones):
```python
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import PasswordChangeView as DjangoPasswordChangeView
from django.urls import reverse_lazy
```

Then append this class to the file:

```python
class PasswordChangeView(BreadcrumbsMixin, LoginRequiredMixin, DjangoPasswordChangeView):
    from .forms import StyledPasswordChangeForm
    form_class = StyledPasswordChangeForm
    template_name = "settings/password.html"
    success_url = reverse_lazy("settings:password")
    breadcrumb_title = "Settings"

    def form_valid(self, form):
        response = super().form_valid(form)
        update_session_auth_hash(self.request, form.user)
        return response
```

**Wait** — `DjangoPasswordChangeView` already calls `update_session_auth_hash` in its own `form_valid`. Verify this before duplicating:

Run: `/Users/silkalns/.local/bin/uv run python -c "import inspect; from django.contrib.auth.views import PasswordChangeView; print(inspect.getsource(PasswordChangeView.form_valid))"`

If the source shows `update_session_auth_hash` is already called, remove the override from our subclass and just subclass cleanly (keep `form_class`, `template_name`, `success_url`, `breadcrumb_title` — nothing else). Django's built-in handles the session-hash update since Django 4.

### Step 2.5 — Wire the URL

In `apps/accounts/settings_urls.py`, replace `path("password/", _PlaceholderView.as_view(), name="password")` with:

```python
    path("password/", PasswordChangeView.as_view(), name="password"),
```

And update the view import at the top:
```python
from .views import ProfileView, PasswordChangeView
```

### Step 2.6 — Create the template `templates/settings/password.html`

```html
{% extends "layouts/settings.html" %}
{% block settings_content %}
<div class="mb-6">
  <h2 class="text-lg font-semibold">Password</h2>
  <p class="text-sm text-muted-foreground">Update your password. You will stay logged in after changing it.</p>
</div>

<form method="post" class="max-w-xl space-y-4">
  {% csrf_token %}
  {% if form.non_field_errors %}
    <div class="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{{ form.non_field_errors }}</div>
  {% endif %}

  <div>
    <label for="{{ form.old_password.id_for_label }}" class="block text-sm font-medium mb-1.5">Current password</label>
    {{ form.old_password }}
    {% if form.old_password.errors %}<p class="text-xs text-destructive mt-1">{{ form.old_password.errors.0 }}</p>{% endif %}
  </div>
  <div>
    <label for="{{ form.new_password1.id_for_label }}" class="block text-sm font-medium mb-1.5">New password</label>
    {{ form.new_password1 }}
    {% if form.new_password1.help_text %}<p class="text-xs text-muted-foreground mt-1">{{ form.new_password1.help_text|safe }}</p>{% endif %}
    {% if form.new_password1.errors %}<p class="text-xs text-destructive mt-1">{{ form.new_password1.errors.0 }}</p>{% endif %}
  </div>
  <div>
    <label for="{{ form.new_password2.id_for_label }}" class="block text-sm font-medium mb-1.5">Confirm new password</label>
    {{ form.new_password2 }}
    {% if form.new_password2.errors %}<p class="text-xs text-destructive mt-1">{{ form.new_password2.errors.0 }}</p>{% endif %}
  </div>

  {% if messages %}
    {% for message in messages %}
      <div class="rounded-md border border-success/30 bg-success/10 p-3 text-sm text-success">{{ message }}</div>
    {% endfor %}
  {% endif %}

  <div class="flex justify-end gap-2">
    <button type="submit" class="h-10 px-4 rounded-md bg-primary text-primary-foreground inline-flex items-center font-medium hover:opacity-90">Update password</button>
  </div>
</form>
{% endblock %}
```

### Step 2.7 — Run tests to verify they pass

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_password_change.py -v 2>&1 | tail -15`
Expected: 5 passed.

### Step 2.8 — Run full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: 106 passed.

### Step 2.9 — Commit

```bash
git add apps/accounts/views.py apps/accounts/forms.py apps/accounts/settings_urls.py templates/settings/password.html apps/accounts/tests/test_password_change.py
git commit -m "$(cat <<'EOF'
feat(settings): Password tab — change password while logged in

Wraps Django's PasswordChangeView with our BreadcrumbsMixin and
BASE_INPUT-styled form. Django's built-in form_valid already calls
update_session_auth_hash so the user stays authenticated after change.

5 unit tests: auth gate, form renders, success path keeps login,
wrong old password rejected, mismatched confirmation rejected.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — Appearance tab

**Files:**
- Modify: `apps/accounts/views.py` (new `AppearanceView`)
- Modify: `apps/accounts/settings_urls.py` (replace placeholder)
- Create: `templates/settings/appearance.html`
- Create: `apps/accounts/tests/test_appearance.py`

### Step 3.1 — Write the failing test

Create `apps/accounts/tests/test_appearance.py`:

```python
import pytest
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_appearance_requires_login(client):
    response = client.get("/settings/appearance/")
    assert response.status_code == 302


def test_appearance_renders_three_options(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/settings/appearance/")
    assert response.status_code == 200
    assert b"Light" in response.content
    assert b"Dark" in response.content
    assert b"System" in response.content
```

### Step 3.2 — Confirm tests fail

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_appearance.py -v 2>&1 | tail -10`
Expected: 2 failures (the placeholder page renders instead of three options).

### Step 3.3 — Add `AppearanceView` to `apps/accounts/views.py`

Append:

```python
from django.views.generic import TemplateView


class AppearanceView(BreadcrumbsMixin, LoginRequiredMixin, TemplateView):
    template_name = "settings/appearance.html"
    breadcrumb_title = "Settings"
```

### Step 3.4 — Wire the URL

In `apps/accounts/settings_urls.py`:
- Update the import: `from .views import ProfileView, PasswordChangeView, AppearanceView`
- Replace `path("appearance/", _PlaceholderView.as_view(), name="appearance")` with:
```python
    path("appearance/", AppearanceView.as_view(), name="appearance"),
```

### Step 3.5 — Create the template `templates/settings/appearance.html`

```html
{% extends "layouts/settings.html" %}
{% load apex %}
{% block settings_content %}
<div class="mb-6">
  <h2 class="text-lg font-semibold">Appearance</h2>
  <p class="text-sm text-muted-foreground">Choose how Apex looks on this device.</p>
</div>

<div x-data="appearancePicker()" x-init="init()" class="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl">
  {# Each card is a radio-like button. Active state derives from `current` #}
  <button type="button"
          @click="setTheme('light')"
          :class="current === 'light' ? 'ring-2 ring-ring border-ring' : 'border-border'"
          class="rounded-lg border bg-card p-5 text-left hover:border-ring transition-colors">
    <div class="flex items-center justify-between mb-3">
      <span class="text-sm font-medium">Light</span>
      {% icon "sun" 18 "text-muted-foreground" %}
    </div>
    <div class="h-20 rounded-md bg-white border border-neutral-200"></div>
  </button>

  <button type="button"
          @click="setTheme('dark')"
          :class="current === 'dark' ? 'ring-2 ring-ring border-ring' : 'border-border'"
          class="rounded-lg border bg-card p-5 text-left hover:border-ring transition-colors">
    <div class="flex items-center justify-between mb-3">
      <span class="text-sm font-medium">Dark</span>
      {% icon "moon" 18 "text-muted-foreground" %}
    </div>
    <div class="h-20 rounded-md bg-neutral-900 border border-neutral-700"></div>
  </button>

  <button type="button"
          @click="setTheme('system')"
          :class="current === 'system' ? 'ring-2 ring-ring border-ring' : 'border-border'"
          class="rounded-lg border bg-card p-5 text-left hover:border-ring transition-colors">
    <div class="flex items-center justify-between mb-3">
      <span class="text-sm font-medium">System</span>
      {% icon "settings" 18 "text-muted-foreground" %}
    </div>
    <div class="h-20 rounded-md bg-gradient-to-r from-white to-neutral-900 border border-border"></div>
  </button>
</div>

<script>
  function appearancePicker() {
    return {
      current: localStorage.getItem("theme") || "system",
      init() {
        // Re-sync if another tab toggled theme
        window.addEventListener("storage", (e) => {
          if (e.key === "theme") this.current = e.newValue || "system";
        });
      },
      setTheme(mode) {
        this.current = mode;
        if (mode === "system") {
          localStorage.removeItem("theme");
          const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
          document.documentElement.classList.toggle("dark", dark);
        } else {
          localStorage.setItem("theme", mode);
          document.documentElement.classList.toggle("dark", mode === "dark");
        }
      },
    };
  }
</script>
{% endblock %}
```

### Step 3.6 — Run tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_appearance.py -v 2>&1 | tail -10`
Expected: 2 passed.

### Step 3.7 — Full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: 108 passed.

### Step 3.8 — Rebuild Tailwind

Run: `npm run build 2>&1 | tail -2`

### Step 3.9 — Commit

```bash
git add apps/accounts/views.py apps/accounts/settings_urls.py templates/settings/appearance.html apps/accounts/tests/test_appearance.py
git commit -m "$(cat <<'EOF'
feat(settings): Appearance tab with Light/Dark/System picker

localStorage-only; System removes the saved key and falls back to
prefers-color-scheme. Picker is an inline Alpine component (own
x-data, no apexShell coupling) — matches the header toggle's write
path so both always agree on state.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — 2FA settings tab

**Files:**
- Modify: `pyproject.toml` (add pyotp, qrcode)
- Create: `apps/accounts/two_factor.py` (model + helpers)
- Create: `apps/accounts/migrations/000N_twofactordevice.py` (generated)
- Modify: `apps/accounts/models.py` (import to register model)
- Modify: `apps/accounts/views.py` (4 new views)
- Modify: `apps/accounts/settings_urls.py` (replace placeholder + add 3 sub-routes)
- Modify: `apps/accounts/forms.py` (3 new forms)
- Create: `templates/settings/two_factor.html`
- Create: `templates/settings/two_factor_setup.html`
- Create: `templates/settings/_recovery_codes_panel.html`
- Create: `apps/accounts/tests/test_two_factor_model.py`
- Create: `apps/accounts/tests/test_two_factor_views.py`

### Step 4.1 — Add dependencies

Edit `pyproject.toml`. Find the `[project.dependencies]` or similar section and add:

```toml
    "pyotp~=2.9",
    "qrcode~=7.4",
```

Then sync:

Run: `/Users/silkalns/.local/bin/uv sync 2>&1 | tail -5`
Expected: pyotp and qrcode listed as added.

### Step 4.2 — Define the model in a new module

Create `apps/accounts/two_factor.py`:

```python
"""TwoFactorDevice model and helpers.

Kept in its own module (rather than models.py) to keep the model file focused
on the User model. Django picks it up because models.py will import it."""

import hashlib
import secrets
from datetime import datetime
from typing import List, Optional

import pyotp
from django.conf import settings
from django.db import models
from django.utils import timezone


# Unambiguous alphabet — excludes O, 0, I, 1.
_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _random_recovery_code() -> str:
    """Format: XXXXX-XXXXX (10 chars + a dash for readability)."""
    left = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(5))
    right = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(5))
    return f"{left}-{right}"


def _hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.upper().encode()).hexdigest()


class TwoFactorDevice(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="two_factor",
    )
    secret = models.CharField(max_length=32)
    confirmed = models.BooleanField(default=False)
    recovery_codes = models.JSONField(default=list)
    # Shape: [{"hash": "<sha256>", "used_at": null | ISO-8601-string}, ...]
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "accounts"

    def __str__(self) -> str:
        status = "on" if self.confirmed else "setup"
        return f"2FA for {self.user.username} ({status})"

    def provisioning_uri(self, issuer: str = "Apex Dashboard") -> str:
        return pyotp.totp.TOTP(self.secret).provisioning_uri(
            name=self.user.username, issuer_name=issuer
        )

    def verify_totp(self, code: str, valid_window: int = 1) -> bool:
        if not code:
            return False
        return pyotp.TOTP(self.secret).verify(code.strip(), valid_window=valid_window)

    def verify_recovery_code(self, code: str) -> bool:
        if not code:
            return False
        target = _hash_recovery_code(code.strip())
        for entry in self.recovery_codes:
            if entry.get("hash") == target and entry.get("used_at") is None:
                entry["used_at"] = timezone.now().isoformat()
                self.save(update_fields=["recovery_codes"])
                return True
        return False

    def generate_recovery_codes(self, count: int = 8) -> List[str]:
        """Replaces existing codes. Returns plaintext — the caller MUST display them."""
        plaintext = [_random_recovery_code() for _ in range(count)]
        self.recovery_codes = [
            {"hash": _hash_recovery_code(c), "used_at": None} for c in plaintext
        ]
        self.save(update_fields=["recovery_codes"])
        return plaintext

    @classmethod
    def create_unconfirmed(cls, user) -> "TwoFactorDevice":
        cls.objects.filter(user=user).delete()
        return cls.objects.create(
            user=user, secret=pyotp.random_base32(), confirmed=False
        )
```

### Step 4.3 — Import the model in `apps/accounts/models.py`

At the bottom of `apps/accounts/models.py`, append:

```python
# Register TwoFactorDevice so migrations/ORM pick it up.
from .two_factor import TwoFactorDevice  # noqa: F401,E402
```

### Step 4.4 — Generate and inspect the migration

Run: `/Users/silkalns/.local/bin/uv run python manage.py makemigrations accounts 2>&1 | tail -5`
Expected: `Migrations for 'accounts': 0002_... Create model TwoFactorDevice`.

Verify the migration file exists under `apps/accounts/migrations/`. Inspect it with `cat apps/accounts/migrations/000*_twofactordevice*.py | head -40` — it should create the table with the 5 fields and a OneToOne constraint on `user_id`.

### Step 4.5 — Apply migration

Run: `/Users/silkalns/.local/bin/uv run python manage.py migrate 2>&1 | tail -5`
Expected: `Applying accounts.000N_... OK`.

### Step 4.6 — Model unit tests

Create `apps/accounts/tests/test_two_factor_model.py`:

```python
import pyotp
import pytest
from apps.accounts.tests.factories import UserFactory
from apps.accounts.two_factor import TwoFactorDevice

pytestmark = pytest.mark.django_db


def test_create_unconfirmed_creates_fresh_device():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    assert d.user_id == user.id
    assert d.confirmed is False
    assert len(d.secret) == 32  # base32-encoded 160 bits = 32 chars


def test_create_unconfirmed_replaces_existing_device():
    user = UserFactory()
    first = TwoFactorDevice.create_unconfirmed(user)
    second = TwoFactorDevice.create_unconfirmed(user)
    assert second.pk != first.pk
    # Only one device per user exists after two creates
    assert TwoFactorDevice.objects.filter(user=user).count() == 1


def test_provisioning_uri_is_valid_otpauth():
    user = UserFactory(username="alice")
    d = TwoFactorDevice.create_unconfirmed(user)
    uri = d.provisioning_uri()
    assert uri.startswith("otpauth://totp/")
    assert "alice" in uri
    assert "Apex%20Dashboard" in uri or "Apex+Dashboard" in uri


def test_verify_totp_accepts_current_window():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    current_code = pyotp.TOTP(d.secret).now()
    assert d.verify_totp(current_code)


def test_verify_totp_rejects_wrong_code():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    assert not d.verify_totp("000000")


def test_generate_recovery_codes_returns_plaintext_stores_hashes():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    codes = d.generate_recovery_codes(count=8)
    assert len(codes) == 8
    for c in codes:
        assert "-" in c and len(c) == 11  # "XXXXX-XXXXX"
    d.refresh_from_db()
    assert len(d.recovery_codes) == 8
    for entry in d.recovery_codes:
        assert entry["used_at"] is None
        assert len(entry["hash"]) == 64  # sha256 hex
    # Raw plaintext MUST NOT be stored
    stored_hashes = {e["hash"] for e in d.recovery_codes}
    plain_as_hash = {__import__("hashlib").sha256(c.upper().encode()).hexdigest() for c in codes}
    assert stored_hashes == plain_as_hash


def test_verify_recovery_code_marks_used_first_time():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    codes = d.generate_recovery_codes()
    code = codes[0]
    assert d.verify_recovery_code(code)
    # Second use fails
    d.refresh_from_db()
    assert not d.verify_recovery_code(code)


def test_verify_recovery_code_case_insensitive():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    codes = d.generate_recovery_codes()
    assert d.verify_recovery_code(codes[0].lower())


def test_verify_recovery_code_rejects_unknown():
    user = UserFactory()
    d = TwoFactorDevice.create_unconfirmed(user)
    d.generate_recovery_codes()
    assert not d.verify_recovery_code("XXXXX-XXXXX")
```

### Step 4.7 — Run model tests to confirm they pass

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_two_factor_model.py -v 2>&1 | tail -20`
Expected: 9 passed.

### Step 4.8 — Add 2FA forms to `apps/accounts/forms.py`

Append at the bottom:

```python
from django.contrib.auth import authenticate


class TwoFactorSetupForm(forms.Form):
    code = forms.CharField(
        max_length=6, min_length=6,
        widget=forms.TextInput(attrs={
            "class": BASE_INPUT + " font-mono tracking-widest text-center",
            "inputmode": "numeric",
            "autocomplete": "one-time-code",
            "placeholder": "123456",
        }),
    )


class TwoFactorDisableForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": BASE_INPUT,
            "autocomplete": "current-password",
            "placeholder": "Your password",
        }),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        pw = self.cleaned_data["password"]
        if authenticate(username=self.user.username, password=pw) is None:
            raise forms.ValidationError("Incorrect password.")
        return pw


class TwoFactorEnableForm(TwoFactorDisableForm):
    """Same as Disable — password confirmation only."""
    pass
```

### Step 4.9 — Add 2FA views

At the top of `apps/accounts/views.py`, add:
```python
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
import io
import qrcode
import qrcode.image.svg
from .two_factor import TwoFactorDevice
from .forms import TwoFactorEnableForm, TwoFactorDisableForm, TwoFactorSetupForm
```

Append these views:

```python
class TwoFactorView(BreadcrumbsMixin, LoginRequiredMixin, View):
    breadcrumb_title = "Settings"

    def get(self, request):
        device = TwoFactorDevice.objects.filter(user=request.user).first()
        flash_codes = None
        # One-shot recovery codes surfaced via messages tagged "recovery_codes"
        for m in messages.get_messages(request):
            if "recovery_codes" in (m.extra_tags or ""):
                flash_codes = m.message  # list of plaintext codes
        return render(request, "settings/two_factor.html", {
            "device": device,
            "confirmed": device.confirmed if device else False,
            "has_unconfirmed": bool(device and not device.confirmed),
            "enable_form": TwoFactorEnableForm(user=request.user),
            "disable_form": TwoFactorDisableForm(user=request.user),
            "flash_codes": flash_codes,
        })


class TwoFactorEnableView(LoginRequiredMixin, View):
    def post(self, request):
        form = TwoFactorEnableForm(request.POST, user=request.user)
        if form.is_valid():
            TwoFactorDevice.create_unconfirmed(request.user)
            return redirect("settings:two_factor_setup")
        messages.error(request, "Password incorrect.")
        return redirect("settings:two_factor")


class TwoFactorSetupView(LoginRequiredMixin, View):
    def _get_unconfirmed(self, request):
        d = TwoFactorDevice.objects.filter(user=request.user, confirmed=False).first()
        if not d:
            return None
        return d

    def get(self, request):
        device = self._get_unconfirmed(request)
        if not device:
            return redirect("settings:two_factor")
        qr_svg = self._render_qr(device.provisioning_uri())
        return render(request, "settings/two_factor_setup.html", {
            "device": device,
            "qr_svg": qr_svg,
            "form": TwoFactorSetupForm(),
        })

    def post(self, request):
        device = self._get_unconfirmed(request)
        if not device:
            return redirect("settings:two_factor")
        form = TwoFactorSetupForm(request.POST)
        if form.is_valid() and device.verify_totp(form.cleaned_data["code"]):
            device.confirmed = True
            device.confirmed_at = timezone.now()
            device.save(update_fields=["confirmed", "confirmed_at"])
            codes = device.generate_recovery_codes()
            messages.success(request, codes, extra_tags="recovery_codes")
            return redirect("settings:two_factor")
        form.add_error("code", "Invalid code. Check your authenticator and try again.")
        qr_svg = self._render_qr(device.provisioning_uri())
        return render(request, "settings/two_factor_setup.html", {
            "device": device, "qr_svg": qr_svg, "form": form,
        })

    @staticmethod
    def _render_qr(uri: str) -> str:
        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(uri, image_factory=factory, box_size=10, border=2)
        buf = io.BytesIO()
        img.save(buf)
        return buf.getvalue().decode()


class TwoFactorDisableView(LoginRequiredMixin, View):
    def post(self, request):
        form = TwoFactorDisableForm(request.POST, user=request.user)
        if form.is_valid():
            TwoFactorDevice.objects.filter(user=request.user).delete()
            messages.success(request, "Two-factor authentication disabled.")
        else:
            messages.error(request, "Password incorrect; 2FA still active.")
        return redirect("settings:two_factor")


class TwoFactorRegenerateView(LoginRequiredMixin, View):
    def post(self, request):
        form = TwoFactorDisableForm(request.POST, user=request.user)
        device = TwoFactorDevice.objects.filter(user=request.user, confirmed=True).first()
        if form.is_valid() and device:
            codes = device.generate_recovery_codes()
            messages.success(request, codes, extra_tags="recovery_codes")
        else:
            messages.error(request, "Password incorrect; codes unchanged.")
        return redirect("settings:two_factor")
```

Also add `from django.utils import timezone` at the top if not already imported.

### Step 4.10 — Wire the URLs

In `apps/accounts/settings_urls.py`:
- Import: `from .views import ProfileView, PasswordChangeView, AppearanceView, TwoFactorView, TwoFactorEnableView, TwoFactorSetupView, TwoFactorDisableView, TwoFactorRegenerateView`
- Replace `path("two-factor/", _PlaceholderView.as_view(), name="two_factor")` with:
```python
    path("two-factor/", TwoFactorView.as_view(), name="two_factor"),
    path("two-factor/enable/", TwoFactorEnableView.as_view(), name="two_factor_enable"),
    path("two-factor/setup/", TwoFactorSetupView.as_view(), name="two_factor_setup"),
    path("two-factor/disable/", TwoFactorDisableView.as_view(), name="two_factor_disable"),
    path("two-factor/regenerate/", TwoFactorRegenerateView.as_view(), name="two_factor_regenerate"),
```

### Step 4.11 — Create the recovery-codes partial

Create `templates/settings/_recovery_codes_panel.html`:

```html
{% if flash_codes %}
<section aria-live="polite"
         class="rounded-lg border border-success/30 bg-success/5 p-5 max-w-2xl">
  <h3 class="text-base font-semibold text-success">Recovery codes</h3>
  <p class="text-sm text-muted-foreground mt-1 mb-4">
    Save these in a safe place. Each one can be used once if you lose access to your authenticator app.
  </p>
  <ul x-data class="grid grid-cols-2 gap-2 font-mono text-sm">
    {% for code in flash_codes %}
      <li class="rounded bg-muted px-3 py-1.5 select-all">{{ code }}</li>
    {% endfor %}
  </ul>
  <button type="button"
          x-data
          @click="navigator.clipboard.writeText($el.parentElement.querySelector('ul').innerText)"
          class="mt-4 h-9 px-3 rounded-md border border-border inline-flex items-center text-sm hover:bg-accent">
    Copy all
  </button>
</section>
{% endif %}
```

### Step 4.12 — Create `templates/settings/two_factor.html`

```html
{% extends "layouts/settings.html" %}
{% block settings_content %}
<div class="mb-6">
  <h2 class="text-lg font-semibold">Two-factor authentication</h2>
  <p class="text-sm text-muted-foreground">Add a second step to every sign-in using a TOTP authenticator app.</p>
</div>

{% include "settings/_recovery_codes_panel.html" %}

{% if confirmed %}
  <section class="rounded-lg border border-border bg-card p-6 mt-6 max-w-2xl">
    <div class="flex items-center gap-2 mb-2">
      <span class="text-xs uppercase tracking-wider rounded-full px-2 py-0.5 bg-success/15 text-success font-semibold">Active</span>
    </div>
    <p class="text-sm text-muted-foreground">Two-factor authentication is enabled. Keep your recovery codes somewhere safe.</p>

    <form method="post" action="{% url 'settings:two_factor_regenerate' %}" class="mt-6 flex items-end gap-3">
      {% csrf_token %}
      <div class="flex-1">
        <label class="block text-sm font-medium mb-1.5">Password</label>
        <input type="password" name="password" required autocomplete="current-password"
               class="w-full h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring/50">
      </div>
      <button type="submit" class="h-10 px-3 rounded-md border border-border inline-flex items-center text-sm hover:bg-accent">Regenerate codes</button>
    </form>

    <form method="post" action="{% url 'settings:two_factor_disable' %}" class="mt-4 flex items-end gap-3">
      {% csrf_token %}
      <div class="flex-1">
        <label class="block text-sm font-medium mb-1.5">Confirm password to disable</label>
        <input type="password" name="password" required autocomplete="current-password"
               class="w-full h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring/50">
      </div>
      <button type="submit" class="h-10 px-3 rounded-md border border-destructive text-destructive inline-flex items-center text-sm hover:bg-destructive hover:text-destructive-foreground transition-colors">Disable 2FA</button>
    </form>
  </section>
{% elif has_unconfirmed %}
  <section class="rounded-lg border border-border bg-card p-6 mt-6 max-w-2xl">
    <p class="text-sm">You started setup but didn't finish.</p>
    <a href="{% url 'settings:two_factor_setup' %}" class="mt-3 inline-flex h-10 px-4 rounded-md bg-primary text-primary-foreground items-center font-medium">Finish setup</a>
  </section>
{% else %}
  <section class="rounded-lg border border-border bg-card p-6 mt-6 max-w-2xl">
    <div class="flex items-center gap-2 mb-2">
      <span class="text-xs uppercase tracking-wider rounded-full px-2 py-0.5 bg-muted text-muted-foreground font-semibold">Off</span>
    </div>
    <p class="text-sm text-muted-foreground mb-4">Enable 2FA to require a code from your authenticator app at every sign-in.</p>
    <form method="post" action="{% url 'settings:two_factor_enable' %}" class="flex items-end gap-3">
      {% csrf_token %}
      <div class="flex-1">
        <label class="block text-sm font-medium mb-1.5">Confirm password</label>
        <input type="password" name="password" required autocomplete="current-password"
               class="w-full h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring/50">
      </div>
      <button type="submit" class="h-10 px-4 rounded-md bg-primary text-primary-foreground inline-flex items-center font-medium">Enable 2FA</button>
    </form>
  </section>
{% endif %}

{% if messages %}
  {% for message in messages %}
    {% if "recovery_codes" not in message.tags %}
      <div class="mt-4 max-w-2xl rounded-md border border-border bg-muted p-3 text-sm">{{ message }}</div>
    {% endif %}
  {% endfor %}
{% endif %}
{% endblock %}
```

### Step 4.13 — Create `templates/settings/two_factor_setup.html`

```html
{% extends "layouts/settings.html" %}
{% block settings_content %}
<div class="mb-6">
  <h2 class="text-lg font-semibold">Set up two-factor</h2>
  <p class="text-sm text-muted-foreground">Scan the QR with your authenticator app, then enter the code below.</p>
</div>

<div class="grid md:grid-cols-2 gap-6 max-w-3xl">
  <section class="rounded-lg border border-border bg-card p-6">
    <div class="mx-auto max-w-[240px]">{{ qr_svg|safe }}</div>
    <p class="mt-4 text-xs text-muted-foreground text-center">Scan with Google Authenticator, 1Password, Authy, or any TOTP app.</p>
  </section>

  <section class="rounded-lg border border-border bg-card p-6">
    <p class="text-sm font-medium mb-2">Can't scan? Enter this key manually:</p>
    <p class="font-mono text-sm break-all bg-muted rounded px-3 py-2 mb-6 select-all">{{ device.secret }}</p>

    <form method="post" class="space-y-4">
      {% csrf_token %}
      <div>
        <label for="{{ form.code.id_for_label }}" class="block text-sm font-medium mb-1.5">Verification code</label>
        {{ form.code }}
        {% if form.code.errors %}<p class="text-xs text-destructive mt-1">{{ form.code.errors.0 }}</p>{% endif %}
      </div>
      <div class="flex gap-2">
        <button type="submit" class="h-10 px-4 rounded-md bg-primary text-primary-foreground inline-flex items-center font-medium">Verify and enable</button>
        <a href="{% url 'settings:two_factor' %}" class="h-10 px-4 rounded-md border border-border inline-flex items-center text-sm hover:bg-accent">Cancel</a>
      </div>
    </form>
  </section>
</div>
{% endblock %}
```

### Step 4.14 — View tests

Create `apps/accounts/tests/test_two_factor_views.py`:

```python
import pyotp
import pytest
from django.urls import reverse
from apps.accounts.tests.factories import UserFactory
from apps.accounts.two_factor import TwoFactorDevice

pytestmark = pytest.mark.django_db


def _login_user(client, password="testpw-x9!"):
    user = UserFactory()
    user.set_password(password)
    user.save()
    client.login(username=user.username, password=password)
    return user


def test_two_factor_view_shows_off_state_for_new_user(client):
    _login_user(client)
    response = client.get("/settings/two-factor/")
    assert response.status_code == 200
    assert b"Enable 2FA" in response.content


def test_enable_requires_correct_password(client):
    user = _login_user(client)
    response = client.post("/settings/two-factor/enable/", {"password": "WRONG"})
    assert response.status_code == 302
    assert not TwoFactorDevice.objects.filter(user=user).exists()


def test_enable_creates_unconfirmed_device_and_redirects_to_setup(client):
    user = _login_user(client, password="good-pass-1")
    response = client.post("/settings/two-factor/enable/", {"password": "good-pass-1"})
    assert response.status_code == 302
    assert response["Location"].endswith("/settings/two-factor/setup/")
    d = TwoFactorDevice.objects.get(user=user)
    assert d.confirmed is False


def test_setup_get_shows_qr_when_unconfirmed_exists(client):
    user = _login_user(client)
    TwoFactorDevice.create_unconfirmed(user)
    response = client.get("/settings/two-factor/setup/")
    assert response.status_code == 200
    assert b"otpauth" not in response.content  # the URI isn't leaked directly
    assert b"<svg" in response.content            # QR SVG rendered
    assert b"Verification code" in response.content


def test_setup_get_redirects_when_no_unconfirmed_device(client):
    _login_user(client)
    response = client.get("/settings/two-factor/setup/")
    assert response.status_code == 302


def test_setup_post_with_valid_code_confirms_and_generates_codes(client):
    user = _login_user(client)
    d = TwoFactorDevice.create_unconfirmed(user)
    code = pyotp.TOTP(d.secret).now()
    response = client.post("/settings/two-factor/setup/", {"code": code}, follow=True)
    d.refresh_from_db()
    assert d.confirmed is True
    assert len(d.recovery_codes) == 8


def test_setup_post_with_invalid_code_renders_error(client):
    user = _login_user(client)
    TwoFactorDevice.create_unconfirmed(user)
    response = client.post("/settings/two-factor/setup/", {"code": "000000"})
    assert response.status_code == 200
    assert b"Invalid code" in response.content
    d = TwoFactorDevice.objects.get(user=user)
    assert d.confirmed is False


def test_disable_requires_password(client):
    user = _login_user(client, password="mypass-9")
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    response = client.post("/settings/two-factor/disable/", {"password": "WRONG"})
    assert TwoFactorDevice.objects.filter(user=user).exists()

    response = client.post("/settings/two-factor/disable/", {"password": "mypass-9"})
    assert not TwoFactorDevice.objects.filter(user=user).exists()
```

### Step 4.15 — Run all Task 4 tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_two_factor_model.py apps/accounts/tests/test_two_factor_views.py -v 2>&1 | tail -30`
Expected: 17 passed (9 model + 8 view).

### Step 4.16 — Run full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: 125 passed.

### Step 4.17 — Rebuild Tailwind

Run: `npm run build 2>&1 | tail -2`

### Step 4.18 — Commit

```bash
git add pyproject.toml uv.lock apps/accounts/two_factor.py apps/accounts/models.py apps/accounts/views.py apps/accounts/forms.py apps/accounts/settings_urls.py apps/accounts/migrations/ templates/settings/two_factor.html templates/settings/two_factor_setup.html templates/settings/_recovery_codes_panel.html apps/accounts/tests/test_two_factor_model.py apps/accounts/tests/test_two_factor_views.py
git commit -m "$(cat <<'EOF'
feat(settings): Two-factor settings tab with QR + recovery codes

Custom TwoFactorDevice model (one per user), TOTP via pyotp, QR via
qrcode (SVG, no PIL). Recovery codes stored as sha256 hashes in a
JSONField; plaintext shown exactly once via messages flash.

Enable requires password; setup GET renders QR + manual-entry key;
setup POST verifies TOTP and generates 8 recovery codes. Disable and
Regenerate are POST-only and also require password.

17 unit tests cover the model + all views.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — 2FA login challenge

**Files:**
- Modify: `apps/accounts/views.py` (add `TwoFactorAwareLoginView`, `TwoFactorChallengeView`)
- Modify: `apps/accounts/forms.py` (add `TwoFactorChallengeForm`)
- Modify: `apex/urls.py` (swap the login view, add challenge route)
- Create: `templates/registration/two_factor_challenge.html`
- Create: `apps/accounts/tests/test_two_factor_challenge.py`

### Step 5.1 — Challenge form

At the bottom of `apps/accounts/forms.py`, append:

```python
class TwoFactorChallengeForm(forms.Form):
    code = forms.CharField(
        max_length=12,  # accommodates "XXXXX-XXXXX" (11) + safety
        widget=forms.TextInput(attrs={
            "class": BASE_INPUT + " font-mono tracking-widest text-center",
            "autocomplete": "one-time-code",
            "inputmode": "text",
            "placeholder": "123456 or recovery code",
        }),
    )
```

### Step 5.2 — Views

At the top of `apps/accounts/views.py`, add:
```python
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.shortcuts import get_object_or_404
from .forms import TwoFactorChallengeForm
```

Append:

```python
class TwoFactorAwareLoginView(DjangoLoginView):
    """LoginView that redirects confirmed-2FA users to the challenge step."""

    def form_valid(self, form):
        user = form.get_user()
        device = getattr(user, "two_factor", None)
        if device and device.confirmed:
            self.request.session["pre_2fa_user_id"] = user.pk
            self.request.session["pre_2fa_next"] = self.get_success_url()
            return HttpResponseRedirect(reverse("two_factor_challenge"))
        return super().form_valid(form)


class TwoFactorChallengeView(View):
    def get(self, request):
        if "pre_2fa_user_id" not in request.session:
            return redirect("login")
        return render(request, "registration/two_factor_challenge.html", {
            "form": TwoFactorChallengeForm(),
        })

    def post(self, request):
        uid = request.session.get("pre_2fa_user_id")
        if not uid:
            return redirect("login")

        User_ = get_user_model()
        user = get_object_or_404(User_, pk=uid)
        form = TwoFactorChallengeForm(request.POST)

        if form.is_valid():
            code = form.cleaned_data["code"].strip()
            device = user.two_factor
            # Numeric TOTP first (shorter strings), else recovery code
            if len(code) == 6 and code.isdigit():
                ok = device.verify_totp(code)
            else:
                ok = device.verify_recovery_code(code)
            if ok:
                next_url = request.session.pop("pre_2fa_next", None) or settings.LOGIN_REDIRECT_URL
                request.session.pop("pre_2fa_user_id", None)
                user.backend = "django.contrib.auth.backends.ModelBackend"
                auth_login(request, user)
                return HttpResponseRedirect(next_url)
            form.add_error("code", "Invalid code. Try again or use a recovery code.")

        return render(request, "registration/two_factor_challenge.html", {"form": form})
```

### Step 5.3 — Wire URLs in `apex/urls.py`

Replace:
```python
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
```
with:
```python
    path("accounts/login/",
         TwoFactorAwareLoginView.as_view(template_name="registration/login.html"),
         name="login"),
    path("accounts/two-factor/", TwoFactorChallengeView.as_view(), name="two_factor_challenge"),
```

Add this import at the top of `apex/urls.py` (with the other imports):
```python
from apps.accounts.views import TwoFactorAwareLoginView, TwoFactorChallengeView
```

### Step 5.4 — Create `templates/registration/two_factor_challenge.html`

```html
{% extends "layouts/auth.html" %}
{% block title %}Two-factor code · Apex{% endblock %}
{% block auth_content %}
<h1 class="text-2xl font-bold tracking-tight mb-1">Two-factor code</h1>
<p class="text-sm text-muted-foreground mb-6">Enter the 6-digit code from your authenticator app, or a recovery code.</p>

<form method="post" class="space-y-4">
  {% csrf_token %}
  {% if form.non_field_errors %}
    <p class="text-xs text-destructive">{{ form.non_field_errors }}</p>
  {% endif %}

  <div>
    <label for="{{ form.code.id_for_label }}" class="sr-only">Code</label>
    {{ form.code }}
    {% if form.code.errors %}<p class="text-xs text-destructive mt-1">{{ form.code.errors.0 }}</p>{% endif %}
  </div>

  <button type="submit" class="w-full h-10 rounded-md bg-primary text-primary-foreground font-medium">Verify</button>
</form>

<div class="mt-4 text-sm text-center">
  <a href="{% url 'login' %}" class="text-muted-foreground hover:text-primary">Back to sign in</a>
</div>
{% endblock %}
```

### Step 5.5 — Tests

Create `apps/accounts/tests/test_two_factor_challenge.py`:

```python
import pyotp
import pytest
from django.urls import reverse
from apps.accounts.tests.factories import UserFactory
from apps.accounts.two_factor import TwoFactorDevice

pytestmark = pytest.mark.django_db


def _user_with_2fa(password="pw-x9!"):
    user = UserFactory()
    user.set_password(password)
    user.save()
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    d.generate_recovery_codes()
    return user, d


def test_login_without_2fa_logs_in_directly(client):
    user = UserFactory()
    user.set_password("pw-x9!")
    user.save()
    response = client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    assert response.status_code == 302
    assert response["Location"] in ("/", "/accounts/profile/")  # LOGIN_REDIRECT_URL defaults
    # Not intercepted by 2FA challenge
    assert "two-factor" not in response["Location"]


def test_login_with_2fa_redirects_to_challenge(client):
    user, _ = _user_with_2fa(password="pw-x9!")
    response = client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    assert response.status_code == 302
    assert response["Location"].endswith("/accounts/two-factor/")
    # User is NOT logged in yet
    assert "_auth_user_id" not in client.session


def test_challenge_get_redirects_to_login_without_session_key(client):
    response = client.get("/accounts/two-factor/")
    assert response.status_code == 302
    assert response["Location"].endswith("/accounts/login/")


def test_challenge_post_valid_totp_completes_login(client):
    user, d = _user_with_2fa(password="pw-x9!")
    client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    code = pyotp.TOTP(d.secret).now()
    response = client.post("/accounts/two-factor/", {"code": code})
    assert response.status_code == 302
    assert response["Location"] != reverse("login")
    assert client.session["_auth_user_id"] == str(user.pk)


def test_challenge_post_valid_recovery_code_completes_login(client):
    user, d = _user_with_2fa(password="pw-x9!")
    client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    codes = d.generate_recovery_codes()
    response = client.post("/accounts/two-factor/", {"code": codes[0]})
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)
    # And that code is now consumed
    d.refresh_from_db()
    used = [e for e in d.recovery_codes if e["used_at"] is not None]
    assert len(used) == 1


def test_challenge_post_wrong_code_renders_error(client):
    user, _ = _user_with_2fa(password="pw-x9!")
    client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    response = client.post("/accounts/two-factor/", {"code": "000000"})
    assert response.status_code == 200
    assert b"Invalid code" in response.content
    assert "_auth_user_id" not in client.session
```

### Step 5.6 — Run challenge tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/accounts/tests/test_two_factor_challenge.py -v 2>&1 | tail -15`
Expected: 6 passed.

### Step 5.7 — Run full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: 131 passed (125 + 6).

### Step 5.8 — Commit

```bash
git add apps/accounts/views.py apps/accounts/forms.py apex/urls.py templates/registration/two_factor_challenge.html apps/accounts/tests/test_two_factor_challenge.py
git commit -m "$(cat <<'EOF'
feat(accounts): 2FA login challenge after password auth

TwoFactorAwareLoginView subclasses Django's LoginView. On successful
password auth, if the user has a confirmed TwoFactorDevice, stash the
user id in session and redirect to /accounts/two-factor/ — session
login does not complete until a valid TOTP or recovery code is posted.

Users without 2FA keep the existing flow.

6 unit tests cover the entire chain: non-2FA user direct login, 2FA
redirect, missing-session guard, valid TOTP success, recovery code
success + mark-used, invalid code error.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — E2E tests

**Files:**
- Create: `tests/e2e/test_settings.py`

### Step 6.1 — Write the four E2E tests

```python
import pyotp
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="demo1234"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_settings_tabs_navigate_and_highlight_active(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/settings/")
    # Redirects to /settings/profile/
    page.wait_for_url(f"{server_url}/settings/profile/")
    # Left-rail has all 4 tabs
    assert page.locator('nav[aria-label="Settings"] a:has-text("Profile")').count() == 1
    assert page.locator('nav[aria-label="Settings"] a:has-text("Password")').count() == 1
    assert page.locator('nav[aria-label="Settings"] a:has-text("Appearance")').count() == 1
    assert page.locator('nav[aria-label="Settings"] a:has-text("Two-factor")').count() == 1
    # Click Password, URL changes, active state moves
    page.click('nav[aria-label="Settings"] a:has-text("Password")')
    page.wait_for_url(f"{server_url}/settings/password/")


def test_enable_2fa_end_to_end(page, server_url, django_user_model):
    # Make a fresh user with a known password so we can POST the enable form
    user = django_user_model.objects.create_user(
        username="alice", password="alicepass1", is_staff=False,
    )
    _login(page, server_url, username="alice", password="alicepass1")
    page.goto(f"{server_url}/settings/two-factor/")
    # Confirm password in the Enable form and submit
    page.fill('form[action$="/enable/"] input[name="password"]', "alicepass1")
    page.click('form[action$="/enable/"] button[type="submit"]')
    page.wait_for_url(f"{server_url}/settings/two-factor/setup/")
    # Pull the device's secret via ORM so we can compute a valid TOTP
    from apps.accounts.two_factor import TwoFactorDevice
    d = TwoFactorDevice.objects.get(user=user, confirmed=False)
    code = pyotp.TOTP(d.secret).now()
    page.fill('input[name="code"]', code)
    page.click('button:has-text("Verify and enable")')
    page.wait_for_url(f"{server_url}/settings/two-factor/")
    # Recovery codes panel should render with 8 codes
    assert page.locator("section[aria-live='polite']").is_visible()
    assert page.locator("section[aria-live='polite'] li").count() == 8


def test_login_with_2fa_requires_challenge(page, server_url, django_user_model):
    from apps.accounts.two_factor import TwoFactorDevice
    user = django_user_model.objects.create_user(username="bob", password="bobpass1", is_staff=False)
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    d.generate_recovery_codes()

    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", "bob")
    page.fill("#id_password", "bobpass1")
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/accounts/two-factor/")
    code = pyotp.TOTP(d.secret).now()
    page.fill('input[name="code"]', code)
    page.click('button:has-text("Verify")')
    page.wait_for_url(f"{server_url}/")


def test_appearance_picker_toggles_dark(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/settings/appearance/")
    page.click('button:has-text("Dark")')
    # HTML element gets the dark class
    is_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
    assert is_dark
    stored = page.evaluate("() => localStorage.getItem('theme')")
    assert stored == "dark"
```

### Step 6.2 — Run the E2E tests

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/test_settings.py -m e2e -v 2>&1 | tail -20`
Expected: 4 passed.

If any test fails:
- Tab-navigation failures → inspect `templates/layouts/settings.html` active-state classes
- 2FA enable failure → check the enable form selector (`form[action$="/enable/"]`) resolves
- Login-challenge failure → may need to wait for `apexShell` hydration (import the existing `wait_for_function` helper or add one)
- Appearance failure → confirm the Alpine component actually writes localStorage (dev tools sometimes block it in headless mode; this is specifically why we use `.evaluate()` rather than reading through Playwright's storage API)

### Step 6.3 — Full suite sanity

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -q 2>&1 | tail -3`
Expected: 131 passed (unchanged).

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/ -m e2e -q 2>&1 | tail -3`
Expected: 10 passed (6 shell + 4 settings).

### Step 6.4 — Commit

```bash
git add tests/e2e/test_settings.py
git commit -m "$(cat <<'EOF'
test(e2e): settings tabs + 2FA setup + 2FA login + appearance picker

Four Playwright tests exercising the Phase 2 surface end-to-end:
- Settings tabs navigate and highlight
- Enable 2FA: QR → valid TOTP → recovery codes appear
- Login with confirmed 2FA: redirect to challenge, TOTP accepted
- Appearance picker: Dark toggles documentElement class + localStorage

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Done — Phase 2 complete

Summary:
- 6 commits on `phase2-settings` branch
- 4 new tabs (Profile moved, Password, Appearance, Two-factor)
- Full 2FA feature: enable, disable, regenerate codes, login challenge
- +30 unit tests, +4 E2E tests (131 unit, 10 E2E total)
- 2 new dependencies (pyotp, qrcode) — both pure Python

After Task 6 passes, this branch is ready to merge to main via `finishing-a-development-branch`.

Next up: Phase 3 — auth completion (verify-email + confirm-password). Separate brainstorm + spec + plan.
