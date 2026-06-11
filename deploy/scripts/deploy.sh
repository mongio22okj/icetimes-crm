#!/usr/bin/env bash
# Deploy the Apex Django demo on the Laravel server.
#
# Usage (run as the apex user, or via sudo -u apex):
#   /var/www/apex-django/deploy/scripts/deploy.sh
#
# What it does (idempotent — safe to re-run):
#   1. source /etc/apex-django.env  (DJANGO_SETTINGS_MODULE, DATABASE_URL, …)
#   2. git pull
#   3. uv sync (Python deps)
#   4. npm install + npm run build (Tailwind CSS)
#   5. python manage.py migrate          (against Postgres in prod)
#   6. python manage.py collectstatic --no-input
#   7. systemctl reload-or-restart apex-django  (graceful Daphne reload)
#
# Set APP_DIR if you cloned somewhere other than /var/www/apex-django.
#
# Requires a sudoers NOPASSWD entry for the reload step. Example
# (drop into /etc/sudoers.d/apex-deploy, validate with `visudo -cf`):
#   apex ALL=(root) NOPASSWD: /bin/systemctl reload-or-restart apex-django, \
#                             /bin/systemctl restart apex-django

set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/apex-django}"
SERVICE="${SERVICE:-apex-django}"
ENV_FILE="${ENV_FILE:-/etc/apex-django.env}"

cd "$APP_DIR"

# Load prod env so migrate/collectstatic target the real database and not
# the dev default (SQLite). Exporting via `set -a` so child processes see
# every var defined in the file.
if [ -r "$ENV_FILE" ]; then
  echo "→ source $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

echo "→ git pull"
git pull --ff-only

echo "→ uv sync (Python deps; --extra realtime if REDIS_URL is set)"
if [ -n "${REDIS_URL:-}" ]; then
  uv sync --extra realtime
else
  uv sync
fi

echo "→ npm ci + Tailwind build"
npm ci
npm run build

echo "→ migrate"
uv run python manage.py migrate --no-input

echo "→ collectstatic"
uv run python manage.py collectstatic --no-input

echo "→ reload Daphne (systemctl)"
# Reload-or-restart: SIGHUP if supported, otherwise restart.
# -n: non-interactive, fails fast if NOPASSWD sudoers entry is missing
# rather than hanging on a password prompt.
sudo -n systemctl reload-or-restart "$SERVICE"

echo "✓ deployed at $(date -u +%FT%TZ)"
