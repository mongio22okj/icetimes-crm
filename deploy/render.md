# Deploy on Render

Render's blueprint-based deploy provisions everything Apex needs in a
single click: a Daphne web service, a managed Postgres 16 instance,
and a managed Redis instance — all auto-wired by env vars.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/puikinsh/dashboardpack-apex-django)

## What you'll get

- **Web service** running Daphne ASGI on Python 3.12+
- **Postgres 16** managed DB (free tier 1GB / 90-day expiration; bump to Starter $7/mo for production)
- **Redis** managed instance (free tier 25MB; bump to Starter $10/mo for production)
- **Auto-deploy on push** — every commit to `main` triggers a build
- **Free `.onrender.com` subdomain** (custom domain settable in dashboard)
- **Free TLS** via Let's Encrypt (managed by Render)

## What it costs

- **Free tier:** $0/mo, suitable for a demo or staging environment.
  Free web spins down after 15 min of inactivity (cold-start ~30s on
  next request — fine for low-traffic demos).
- **Starter tier:** ~$24/mo total ($7 web + $7 db + $10 redis), no
  cold starts, larger DB + Redis allotments.

## Click-to-deploy walkthrough

### 1. Click the "Deploy to Render" button above

Sign in with GitHub (Render reads the `deploy/render.yaml` blueprint
from your fork). You'll see a **Blueprint Preview** showing the three
services Render will create.

### 2. Override the demo defaults if needed

The blueprint defaults to demo mode (login form pre-fills credentials).
For a real production deploy:

| Env var | Default | Change to |
|---|---|---|
| `DEMO_MODE` | `"true"` | `"false"` |
| `ALLOWED_HOSTS` | `".onrender.com"` | `"app.yourdomain.com,.onrender.com"` |

### 3. Click "Apply"

Render provisions the services. First deploy takes ~5–8 minutes
(building Tailwind + npm deps + collectstatic + migrate + seed_demo).
Watch the build log live in the Render dashboard.

### 4. Visit your `.onrender.com` URL

The build script seeded demo data, so you can sign in immediately
with `demo` / `ApexShowcase!2026`.

## Adding a custom domain

1. **Render dashboard → web service → Settings → Custom Domains → Add**
2. Add your domain (e.g. `app.yourdomain.com`)
3. Add a CNAME record at your DNS provider:
   `app  CNAME  apex-django-XXX.onrender.com`
4. **Update `ALLOWED_HOSTS`** in the web service Environment to include
   your custom domain
5. Render auto-issues a Let's Encrypt cert within 1–2 minutes

## Removing the demo seed (real production)

Edit `deploy/render.yaml` and remove this line from `buildCommand`:

```yaml
uv run python manage.py seed_demo
```

Then create a fresh DB (or `python manage.py flush --no-input` once)
and redeploy. Set `DEMO_MODE=false` while you're at it.

## Optional: Sentry + email + metrics

Uncomment + set in the **Environment** tab of the Render web service:

```
SENTRY_DSN          = https://....ingest.sentry.io/...
SENTRY_ENV          = production
DEFAULT_FROM_EMAIL  = Apex <hello@yourdomain.com>
EMAIL_HOST          = smtp.yourdomain.com
EMAIL_HOST_USER     = ...
EMAIL_HOST_PASSWORD = ...   (mark "Sync this value to repo" OFF)
METRICS_ENABLED     = true  (only if you have a Prometheus scraper)
```

Restart the service after changing env vars (Render does this
automatically on save).

## Cron jobs (Render Cron)

Render Cron jobs are a separate service type — add them via the
dashboard:

```yaml
# Add to deploy/render.yaml under `services:`
  - type: cron
    name: apex-reset-demo
    runtime: python
    schedule: "5 * * * *"          # hourly at HH:05 UTC
    buildCommand: pip install uv && uv sync --frozen
    command: uv run python manage.py reset_demo --no-input
    envVars:
      - { key: DJANGO_SETTINGS_MODULE, value: apex.settings.prod }
      - { key: SECRET_KEY,             fromService: { type: web, name: apex-django, envVarKey: SECRET_KEY } }
      - { key: DATABASE_URL,           fromDatabase: { name: apex-db, property: connectionString } }
```

Render Cron is paid only ($1/mo per cron), so most demo deploys skip
it and rely on visitor activity to keep things fresh.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Build fails on `npm ci` | Make sure your fork has `package-lock.json` committed |
| Build fails on `weasyprint` import | Render's Python image includes pango/cairo by default — should "just work". If not, add `aptPackages: [libpango-1.0-0, libpangoft2-1.0-0, libcairo2]` under the web service |
| `502 Bad Gateway` after deploy | Daphne crashed at startup — check Logs tab. Usually a missing env var |
| WebSockets won't connect | Render supports WS natively; no extra config needed. If 4401, check CSRF/session cookies are HTTPS-only |
| Free tier sleeps and wakes slowly | That's the trade-off; bump to Starter ($7/mo web) for always-on |
