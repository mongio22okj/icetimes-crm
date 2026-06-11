# Deploying Apex Django on the Laravel server

Hosts at **`apex-django.dashboardpack.com`** alongside the existing PHP
sites. The Laravel templates run on PHP-FPM behind nginx; we slot Apex
in as a separate nginx vhost that proxies to **Daphne** (ASGI) on a
unix socket.

```
Cloudflare ─▶ nginx ─▶ unix:/run/apex-django/apex-django.sock ─▶ Daphne ─▶ Django
                │
                └─▶ /static/ ─▶ /var/www/apex-django/staticfiles/  (served directly)
```

## What you'll touch on the server

| Path | Purpose |
|---|---|
| `/var/www/apex-django/` | Code checkout (git clone target) |
| `/etc/apex-django.env` | Secrets + `DATABASE_URL` (read by systemd) |
| `/etc/systemd/system/apex-django.service` | Daphne unit (this repo: `deploy/systemd/`) |
| `/etc/nginx/sites-available/apex-django.dashboardpack.com.conf` | Vhost (this repo: `deploy/nginx/`) |
| `/etc/ssl/cloudflare/apex-django.dashboardpack.com.{crt,key}` | Cloudflare Origin Cert |
| `/run/apex-django/apex-django.sock` | Daphne socket (auto-created by systemd) |

---

## First-time setup (~15 minutes)

### 1. DNS — point the demo subdomain at the server

In Cloudflare DNS for `dashboardpack.com`:

- **Type:** A · **Name:** `apex-django` · **Target:** server IP · **Proxy:** ✅ orange-cloud

Wait for the `dig apex-django.dashboardpack.com` to come back with a
Cloudflare IP (104.x / 172.x).

### 2. Cloudflare TLS — strict mode + origin cert

- **SSL/TLS → Overview** — set to **Full (strict)**.
- **SSL/TLS → Origin Server → Create Certificate** — accept defaults
  (15-year cert, hostname `apex-django.dashboardpack.com`). Save the
  cert + key.
- On the server:
  ```bash
  sudo mkdir -p /etc/ssl/cloudflare
  sudo nano /etc/ssl/cloudflare/apex-django.dashboardpack.com.crt   # paste
  sudo nano /etc/ssl/cloudflare/apex-django.dashboardpack.com.key   # paste
  sudo chmod 600 /etc/ssl/cloudflare/apex-django.dashboardpack.com.key
  ```
- (Optional but recommended) Authenticated Origin Pulls so only
  Cloudflare can hit the origin on 443:
  ```bash
  sudo curl -o /etc/ssl/cloudflare/authenticated_origin_pull_ca.pem \
    https://developers.cloudflare.com/ssl/static/authenticated_origin_pull_ca.pem
  ```
  Enable in Cloudflare under **SSL/TLS → Origin Server → Authenticated
  Origin Pulls**. The vhost in this repo already has `ssl_verify_client
  on;` — comment it out if you don't enable this.

### 3. System packages

Most are likely already on the Laravel box. The new ones:

```bash
sudo apt update
sudo apt install -y \
  python3.12 python3.12-dev \
  postgresql postgresql-client \
  build-essential libpq-dev \
  libpango-1.0-0 libpangoft2-1.0-0   # WeasyPrint native libs (PDF invoices)
# uv (Python runner used by the systemd unit + deploy script)
curl -LsSf https://astral.sh/uv/install.sh | sudo sh
# Node 20+ for the Tailwind build
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 4. Service user + checkout

```bash
sudo useradd --system --create-home --home-dir /var/www/apex-django \
  --shell /bin/bash apex
sudo usermod -aG www-data apex            # so nginx can read the socket
sudo -u apex git clone <repo-url> /var/www/apex-django
```

### 5. Postgres database

```bash
sudo -u postgres createuser apex_django -P     # set a strong password
sudo -u postgres createdb apex_django -O apex_django
```

Confirm:
```bash
psql "postgres://apex_django:PASSWORD@127.0.0.1:5432/apex_django" -c '\dt'
```

### 6. Environment file

```bash
sudo cp /var/www/apex-django/deploy/.env.example /etc/apex-django.env
sudo chown apex:apex /etc/apex-django.env
sudo chmod 0640 /etc/apex-django.env
sudo nano /etc/apex-django.env
# Fill in: SECRET_KEY (run the one-liner in the file), DATABASE_URL with
# the password you just set, and EMAIL_* if you want password resets.
```

Generate `SECRET_KEY`:
```bash
sudo -u apex bash -c 'cd /var/www/apex-django && uv run python -c "
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())"'
```

### 7. First build + migrate + seed

```bash
sudo -u apex bash <<'EOF'
cd /var/www/apex-django
uv sync                                  # installs Daphne, Channels, etc.
npm ci && npm run build                  # builds static/css/app.css
DJANGO_SETTINGS_MODULE=apex.settings.prod \
  $(grep -v '^#' /etc/apex-django.env | xargs) \
  uv run python manage.py migrate
DJANGO_SETTINGS_MODULE=apex.settings.prod \
  $(grep -v '^#' /etc/apex-django.env | xargs) \
  uv run python manage.py collectstatic --no-input
DJANGO_SETTINGS_MODULE=apex.settings.prod \
  $(grep -v '^#' /etc/apex-django.env | xargs) \
  uv run python manage.py seed_demo
EOF
```

### 8. systemd unit

```bash
sudo cp /var/www/apex-django/deploy/systemd/apex-django.service \
  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now apex-django
sudo systemctl status apex-django           # should be "active (running)"
sudo journalctl -u apex-django -f           # follow logs
```

If status shows ImportError or path issues, double-check:
- `which uv` matches the `ExecStart=` path in the unit
- `User=apex` exists and owns `/var/www/apex-django`
- `/etc/apex-django.env` is mode 0640 owned by apex:apex

### 9. nginx vhost

```bash
sudo cp /var/www/apex-django/deploy/nginx/apex-django.dashboardpack.com.conf \
  /etc/nginx/sites-available/
sudo ln -s ../sites-available/apex-django.dashboardpack.com.conf \
  /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

If `nginx -t` complains about the `map $http_upgrade …` block being
already defined, it means another vhost (often /etc/nginx/conf.d/)
already declares it — delete the `map` block from this vhost and keep
the existing global one.

### 10. Smoke test

```bash
curl -I https://apex-django.dashboardpack.com/
# HTTP/2 302 — redirects to /accounts/login/   ← good
curl -I https://apex-django.dashboardpack.com/accounts/login/
# HTTP/2 200
```

Visit https://apex-django.dashboardpack.com/ in a browser, sign in as
**demo / ApexShowcase!2026** (the demo banner pre-fills it), and open
`/realtime/` in two tabs to confirm WebSockets are reaching Daphne.

---

## Ongoing deploys

```bash
sudo -u apex /var/www/apex-django/deploy/scripts/deploy.sh
```

That's it — pull, deps, migrate, collectstatic, graceful Daphne reload.
Open sessions stay connected.

---

## Coexistence with the Laravel sites — sanity checklist

- [ ] **PHP-FPM untouched** — the new vhost only adds a new
  `server { … server_name apex-django.dashboardpack.com; }` block.
  Existing `dashboardpack.com` / `*.dashboardpack.com` vhosts keep
  routing to PHP-FPM.
- [ ] **Single `map $http_upgrade …` declaration in nginx** — nginx
  errors on duplicate. Move the map to `/etc/nginx/conf.d/upgrade.conf`
  if multiple vhosts need it.
- [ ] **Postgres owns its own DB role** — don't reuse the Laravel app's
  DB user; isolate via `apex_django` so neither side can clobber the
  other's tables.
- [ ] **Static + media paths don't collide** — Apex serves at
  `/static/` and `/media/` *under* `apex-django.dashboardpack.com`.
  Other vhosts' `/static/` aliases are scoped to their own server_name.
- [ ] **firewall** — only ports 80 + 443 need to be open to the
  internet; Daphne's socket is unix-domain (no TCP exposure).

---

## Scaling beyond the demo

Single-process Daphne with the in-memory channel layer is comfortable
for hundreds of concurrent visitors. When you need more:

1. **Install Redis on the box** (`sudo apt install redis-server`).
2. **Set `REDIS_URL`** in `/etc/apex-django.env` —
   `redis://127.0.0.1:6379/0`.
3. **Switch deps** — `sudo -u apex uv sync --extra realtime` (the
   deploy script picks this up automatically when `REDIS_URL` is set).
4. **Run multiple Daphne workers** — duplicate the systemd unit as a
   template (`apex-django@.service`), start `apex-django@1`,
   `apex-django@2`, … and have nginx upstream-balance across the
   sockets.

That moves you from ~few hundred to ~thousands of concurrent users
without leaving this server.

---

## Troubleshooting cheat sheet

| Symptom | Fix |
|---|---|
| `502 Bad Gateway` from nginx | `sudo systemctl status apex-django` — Daphne isn't running. Check `journalctl -u apex-django` for the traceback. |
| `400 Bad Request` from Django | `ALLOWED_HOSTS` mismatch. Domain must be in the env file or hard-pinned in `prod.py` (it is). |
| WebSockets fail with 1006 | nginx vhost missing the `Upgrade`/`Connection` headers in the `/ws/` location. Re-check `deploy/nginx/`. |
| `CSRF verification failed` | `CSRF_TRUSTED_ORIGINS` missing the domain. `prod.py` derives it from `ALLOWED_HOSTS` automatically. |
| Static files 404 | `collectstatic` not run, or nginx `alias` path doesn't match `STATIC_ROOT` (= `/var/www/apex-django/staticfiles/`). |
| Redirect loop on HTTPS | Cloudflare SSL mode must be **Full (strict)**. Flexible mode causes the loop. |
| Origin cert errors after a year | Cloudflare Origin Certs last 15 years by default — if you generated a 1-year one, regenerate at SSL/TLS → Origin Server. |
