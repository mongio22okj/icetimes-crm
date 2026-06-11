# Deploy on Fly.io

Fly is the best choice if you want **multi-region** (run the same
Django + Postgres in 3+ continents and serve users from the closest
edge), **native WebSocket support** (no proxy quirks), or simply a
Docker-based deploy without managing servers.

## What you'll get

- **App service** running Daphne ASGI in a Firecracker microVM
- **Managed Postgres** (Fly's managed Postgres or external)
- **Managed Redis** (via Upstash, integrated)
- **Native WebSocket support** — no special config, `/ws/` just works
- **Free Let's Encrypt** TLS on `*.fly.dev` and any custom domain
- **Optional multi-region failover** — change one config line, get global

## What it costs

Fly's pricing is consumption-based. Realistic monthly bill for the
demo workload (single 256MB VM + free Postgres + free Upstash Redis):
**~$2–5/mo**. For production traffic at 256MB always-on: ~$5–10/mo.
Multi-region 3-VM cluster: ~$15–30/mo.

The free tier covers small Postgres + Redis but VM time is metered —
budget ~$2/mo for a single demo VM running 24/7.

## Prerequisites

```bash
# Install flyctl (the official CLI)
curl -L https://fly.io/install.sh | sh
fly version
```

```bash
# Sign up or log in
fly auth signup    # opens browser; payment method required (no charges if you stay in free allotments)
fly auth login
```

## First-time deploy

### 1. Initialize from the repo

```bash
git clone https://github.com/puikinsh/dashboardpack-apex-django.git
cd dashboardpack-apex-django

# Use the bundled fly.toml (don't let `fly launch` overwrite it)
cp deploy/fly.toml ./fly.toml

fly launch --copy-config --no-deploy
```

`fly launch` will:
- Detect the `fly.toml` already present and use it
- Ask you to pick an app name (must be globally unique — try `apex-django-yourname`)
- Pick a primary region (closest to you or your users)
- **NOT** deploy yet — we still need to provision DB + Redis + secrets

### 2. Provision Postgres

```bash
fly postgres create --name apex-django-db --region iad --vm-size shared-cpu-1x
fly postgres attach apex-django-db
```

`attach` automatically sets the `DATABASE_URL` secret on your app, so
Django picks it up without manual config.

### 3. Provision Redis (via Upstash)

```bash
fly redis create --name apex-django-redis --region iad --plan free
```

When prompted, select **Eviction: yes** and copy the connection URL
shown. Then:

```bash
fly secrets set REDIS_URL="redis://default:....@usw1-....upstash.io:6379"
```

### 4. Set the rest of the required secrets

```bash
fly secrets set \
  SECRET_KEY="$(openssl rand -hex 32)" \
  ALLOWED_HOSTS="apex-django-yourname.fly.dev"
```

For a real production deploy, also:

```bash
fly secrets set DEMO_MODE=false
```

### 5. Deploy

```bash
fly deploy
```

This builds the Dockerfile, pushes to Fly's registry, runs the
release command (`python manage.py migrate`), then rolls out new VMs
behind the health check. ~5 minutes for first deploy; ~2 minutes
after that thanks to layer caching.

### 6. Open the app

```bash
fly open                   # opens the .fly.dev URL in your browser
fly status                 # shows VM state + region + IP allocation
fly logs                   # tail logs (Daphne + Django + Channels)
```

The build script doesn't seed demo data automatically (Fly's release
command runs in a one-shot VM that can't always write to a shared DB
race-free). Seed manually after the first deploy:

```bash
fly ssh console -C "uv run python manage.py seed_demo"
```

## Persistent uploads (Files app, avatars)

The dockerfile is stateless — files uploaded to `/app/user_files/`
disappear on the next deploy. To persist:

```bash
fly volumes create apex_uploads --region iad --size 1
```

Then uncomment the `[[mounts]]` block in `deploy/fly.toml` and
redeploy. The volume mounts at `/app/user_files/` inside the VM.

For multi-region or larger files, swap to S3-compatible object storage
(R2, Backblaze B2, S3 itself) — set Django's `DEFAULT_FILE_STORAGE`
in prod.py to `storages.backends.s3boto3.S3Boto3Storage`.

## Custom domain

```bash
fly certs create app.yourdomain.com
fly certs show app.yourdomain.com   # shows the DNS records to add
```

Add the displayed CNAME / A / AAAA records at your DNS provider.
Fly issues the Let's Encrypt cert within ~2 minutes of DNS propagation.

Then add the new host:

```bash
fly secrets set ALLOWED_HOSTS="app.yourdomain.com,apex-django-yourname.fly.dev"
```

## Multi-region

Adding more regions is trivial:

```bash
fly regions add fra syd       # add Frankfurt + Sydney
fly scale count 3 --region iad,fra,syd   # one VM in each
```

Fly's anycast IPs route each visitor to the nearest VM. Note that
your Postgres still lives in one region — Fly Postgres has read
replicas if you need them, or use a global DB like Neon/Supabase.

## Cron jobs (Fly Machines)

Fly has native scheduled jobs via Machines:

```bash
fly machine run . \
  --name apex-reset-demo \
  --schedule hourly \
  --restart no \
  -- python manage.py reset_demo --no-input
```

Or for a finer schedule (HH:05 UTC like our preview server):

```bash
# Add to fly.toml under [processes]:
[processes]
  app = ""              # default web process
  cron = "while true; do sleep 3600; python manage.py reset_demo --no-input; done"
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `fly deploy` fails on Docker build | Run `docker build .` locally first to catch errors faster |
| App boots but `/__health/` returns 503 | Check `fly logs` — usually `DATABASE_URL` not set, or Postgres unreachable |
| WebSockets disconnect immediately (1006) | Check `fly logs` for CSRF/origin errors; ensure `ALLOWED_HOSTS` includes the domain you're connecting from |
| `502 Bad Gateway` on first request after deploy | Cold start of the new machine — wait 5–10s, retry. Set `min_machines_running = 1` (already done in our fly.toml) |
| Static files 404 | The Dockerfile runs `collectstatic` at build time. If new files don't appear, your build cache might be stale: `fly deploy --no-cache` |
| Out of memory | Bump `memory_mb` in `fly.toml` from 256 → 512 → 1024 |
| Postgres "connection refused" | Run `fly postgres attach apex-django-db` again to reset the secret |
