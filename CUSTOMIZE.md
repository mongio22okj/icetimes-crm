# Customize Apex — your first 10 minutes

Welcome. This is the *first* doc to read after `git clone`. It covers
the five things you almost certainly want to change before deploying
your own version of the template, in priority order.

After this, see [`docs/getting-started.md`](docs/getting-started.md)
for a deeper tour of the architecture, and
[`deploy/README.md`](deploy/README.md) for the production deployment
walkthrough.

---

## 1. Brand name (everywhere it appears)

The string `Apex` shows up in titles, the sidebar logo, marketing pages,
emails, and a few places in the codebase. Search-and-replace covers
most of it:

```bash
# macOS / BSD sed:
grep -rl --include='*.html' --include='*.py' --include='*.md' \
  --exclude-dir=node_modules --exclude-dir=.venv 'Apex' . \
  | xargs sed -i '' 's/Apex/Yourbrand/g'

# GNU sed (Linux):
grep -rl --include='*.html' --include='*.py' --include='*.md' \
  --exclude-dir=node_modules --exclude-dir=.venv 'Apex' . \
  | xargs sed -i 's/Apex/Yourbrand/g'
```

After the bulk replace, verify:

| File | What to check |
|---|---|
| `templates/base.html` | `<title>` block default |
| `templates/partials/sidebar.html` | Sidebar logo word + the `aria-label="Apex home"` |
| `apex/settings/base.py` | `DEMO_USERNAME` / `DEMO_PASSWORD` (only matters if you ship a demo) |
| `apps/marketing/templates/marketing/*.html` | Hero copy, footer copy, OG tags |
| `templates/registration/password_reset_email.{txt,html}` | Email subject + signoff |
| `README.md`, `CHANGELOG.md` | Product name in your fork |

Don't rename the Python package `apex/` itself unless you have a reason
— the directory name is internal-only and renaming it cascades into
`DJANGO_SETTINGS_MODULE`, `WSGI_APPLICATION`, `ASGI_APPLICATION`, and
the systemd unit. Brand is the user-facing string, package name is
your private detail.

---

## 2. Logo + favicon

### Logo

The sidebar logo is an inline SVG square with a Lucide `package` icon
and the brand wordmark next to it. Two ways to swap:

**Option A — keep the icon-in-square, change the icon.** Pick a name
from `apps/core/templatetags/apex.py`'s `ICONS` dict (the Lucide set we
ship) and edit:

```html
<!-- templates/partials/sidebar.html -->
<span class="h-8 w-8 rounded-md bg-primary text-primary-foreground inline-flex items-center justify-center">
  {% icon "rocket" 18 %}   {# ← was "package" #}
</span>
```

**Option B — drop in your own SVG/PNG.** Save it under
`static/img/logo.svg` and replace the `<span>` with:

```html
<img src="{% static 'img/logo.svg' %}" alt="Yourbrand" class="h-8 w-8" />
```

The dashboard layout uses CSS variables for foreground colors; a single-color
SVG with `fill="currentColor"` will pick up the active palette automatically.

### Favicon

There's no shipped favicon — Cloudflare returns 404 for `/favicon.ico`
right now. To add one:

```html
<!-- templates/base.html, inside <head> -->
<link rel="icon" type="image/svg+xml" href="{% static 'img/favicon.svg' %}">
<link rel="icon" type="image/png" href="{% static 'img/favicon.png' %}">
<link rel="apple-touch-icon" href="{% static 'img/apple-touch-icon.png' %}">
```

Save the files in `static/img/` and run `npm run build && python manage.py collectstatic`.

---

## 3. Color palette (design tokens)

All brand colors live in **one file**:
[`static_src/css/input.css`](static_src/css/input.css), under `:root`
(light) and `.dark` (dark). They use OKLCh so any change keeps
perceptual contrast clean.

The "primary" color (buttons, active sidebar item, accent badges) is
the one you'll most want to change:

```css
:root {
  --primary: oklch(0.55 0.25 264);             /* indigo */
  --primary-foreground: oklch(0.985 0 0);
}
.dark {
  --primary: oklch(0.65 0.25 264);
  --primary-foreground: oklch(0.145 0 0);
}
```

After editing, rebuild Tailwind:

```bash
npm run build      # one-shot
npm run dev        # watch mode while iterating
```

For a thorough recolor, change the L (lightness) and C (chroma)
together in matched pairs across both `:root` and `.dark` so contrast
stays balanced. Tools like [oklch.com](https://oklch.com/) help.

---

## 4. Site URL + email defaults (production env)

The two most critical production env vars to set:

```env
# /etc/yourapp.env on the server
ALLOWED_HOSTS=app.yourbrand.com
DEFAULT_FROM_EMAIL=Yourbrand <hello@yourbrand.com>

# SMTP if you actually want password resets / invites to deliver:
EMAIL_HOST=smtp.yourbrand.com
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=true
```

`apex/settings/prod.py` reads these and feeds them to Django's email
backend. Without them, password reset emails go to the console (fine
for dev, useless in prod).

The `apex-django.dashboardpack.com` host is currently pinned in
`prod.py` for the public demo — when you fork this template, edit that
line:

```python
# apex/settings/prod.py
ALLOWED_HOSTS = list({*_env_hosts, "app.yourbrand.com"})  # ← was "apex-django.dashboardpack.com"
```

---

## 5. Cleanup before launch

A few things ship as scaffolding for the demo / template authoring
process. Strip them out for your own deploy:

- **Demo mode banner** — set `DEMO_MODE=false` (or unset) in your env
  file. The login auto-fill banner and the orange "Public demo, data
  resets" bar both gate on this.
- **`seed_demo` command** — keep the file if you want sample data for
  development (`uv run python manage.py seed_demo`), but never run it
  on production. It creates a `demo` user with a known password.
- **CHANGELOG history** — fork-friendly: clear it out and start your
  own `## [1.0.0] - YYYY-MM-DD` line. Or keep ours as upstream
  attribution.
- **Phase planning docs in `docs/superpowers/`** — these are how the
  template was built; they're not relevant to your fork. Delete the
  directory once you've read what you want from it.
- **Sample data in `apps/*/tests/factories.py`** — keep these (tests
  depend on them) but the actual data they generate is only seeded
  when you call `seed_demo`.

---

## What's wired and how to extend each surface

Once the basics above are in place, here's the map:

| Want to add… | Edit |
|---|---|
| A new sidebar item | `apps/core/navigation.py` (single source of truth for sidebar + palette) |
| A new dashboard variant | New CBV in `apps/dashboard/views.py` + URL + template extending `layouts/dashboard.html` |
| A new chart | Alpine factory in `static/js/charts.js` + JSON endpoint in `apps/dashboard/views.py` |
| A new model + admin CRUD | Model → migration → CBV stack with `BreadcrumbsMixin + LoginRequiredMixin + EmailVerifiedRequiredMixin + (StaffRequiredMixin)` → URL → list/detail/form templates |
| A new email | Template under `templates/registration/` (txt + html), wire via Django's `send_mail` or `notify()` (`apps/notifications/dispatch.py`) |
| A new locale | `django-admin makemessages -l <code>` → translate `locale/<code>/LC_MESSAGES/django.po` → `compilemessages` |
| A new API endpoint | Add a router in `apps/api/api.py` (Django Ninja) — auto-OpenAPI at `/api/v1/docs` |
| A realtime push | `apps/realtime/dispatch.push_notification(user_id, payload)` — fans out to every open tab |

For more depth, see [`docs/getting-started.md`](docs/getting-started.md)
and the per-app `CLAUDE.md` notes.

---

## Stuck?

- The architecture doc is [`CLAUDE.md`](CLAUDE.md) (yes, the same file
  the AI uses — it's the most accurate map of how things hang together).
- The full list of features and surfaces is in [`README.md`](README.md).
- The deploy walkthrough is [`deploy/README.md`](deploy/README.md).
- Open an issue / discussion on the GitHub repo — tag with `[customize]`.
