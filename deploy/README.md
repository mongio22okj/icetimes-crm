# Deploy Apex Django

Apex runs anywhere Python + Postgres + Redis run. Pick a path:

| Platform | Best for | Cost (demo) | Setup time |
|---|---|---|---|
| [**Render**](render.md) | Click-to-deploy via blueprint, free tier | $0/mo | ~5 min |
| [**Fly.io**](fly.md) | Multi-region, native WebSocket, Docker-based | ~$2–5/mo | ~10 min |
| [**Linux VPS**](linux-vps.md) | Coexist with other apps on one box (e.g. nginx + PHP-FPM) | $6–20/mo | ~15 min |

All three paths run the **same Django 6 app**, the same `apex/settings/prod.py`,
and consume the same env vars (`SECRET_KEY`, `DATABASE_URL`,
`ALLOWED_HOSTS`, `REDIS_URL`, optional `SENTRY_DSN`, `DEMO_MODE`,
`METRICS_ENABLED`). You can switch between them later without
touching application code.

## What's required regardless of platform

- **Python 3.12+** (Django 6 requires)
- **Postgres 16+** (managed or self-hosted)
- **Redis** (only if you want multi-process WebSocket fan-out;
  optional for single-process deploys)
- A unique value for **`SECRET_KEY`** (generate with
  `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
- The domain in **`ALLOWED_HOSTS`** (e.g. `app.yourdomain.com`)

For SMTP-backed emails (password reset, invitations) also set:
- `DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`

## What's optional

| Feature | Activate by setting |
|---|---|
| Demo mode (login auto-fill, banner, hourly reseed) | `DEMO_MODE=true` |
| Sentry error capture | `SENTRY_DSN=https://...@sentry.io/...` |
| Prometheus metrics at `/__metrics/` | `METRICS_ENABLED=true` (+ `uv sync --extra metrics`) |
| Redis-backed channel layer (multi-process WS fan-out) | `REDIS_URL=redis://...` (+ `uv sync --extra realtime`) |

## Files in this directory

```
deploy/
├── README.md           ← you are here (platform picker)
├── render.md           ← Render walkthrough
├── render.yaml         ← Render blueprint (web + db + redis)
├── fly.md              ← Fly.io walkthrough
├── fly.toml            ← Fly app config
├── linux-vps.md        ← Bare Linux VPS walkthrough (full nginx/systemd setup)
├── nginx/              ← nginx vhost for the VPS path
├── systemd/            ← Daphne systemd unit for the VPS path
├── scripts/            ← deploy.sh + reset_demo_cron.sh for the VPS path
└── .env.example        ← env file template (used by the VPS path)
```

The **`Dockerfile`** in the repo root is shared by Fly + any other
container host (Cloud Run, ECS, k8s) — multi-stage build that outputs
a ~250MB runtime image with Daphne + Channels.

## Picking the right path

- **You want zero-friction evaluation, even on free tier.** → Render
  (free tier sleeps after 15 min of inactivity but wakes on next
  request — fine for sharing a demo URL with prospects)
- **You need WebSockets to be rock-solid + multi-region.** → Fly.io
- **You already have a Linux box running other sites and want to
  coexist.** → Linux VPS
- **You want to host on your existing Docker / Kubernetes / ECS
  infrastructure.** → Use the root `Dockerfile`, set env vars
  per the platform picker. The fly.toml pattern shows what env vars +
  health check path to wire up.
