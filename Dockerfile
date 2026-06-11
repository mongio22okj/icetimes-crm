# syntax=docker/dockerfile:1

# ===== Stage 1: build the Tailwind CSS bundle =====
FROM node:20-slim AS css-builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# Copy only what Tailwind v4 scans (templates + apps) so a Python-only
# change doesn't bust the css cache.
COPY tailwind.config.js postcss.config.js ./
COPY static_src/ ./static_src/
COPY templates/ ./templates/
COPY apps/ ./apps/

RUN npx @tailwindcss/cli -i ./static_src/css/input.css -o ./static/css/app.css --minify


# ===== Stage 2: Python application =====
FROM python:3.13-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=apex.settings.prod \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# WeasyPrint native libs + gettext for compilemessages
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        gettext \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency management
RUN pip install uv

# Python deps — copy lockfile first for layer caching.
# `realtime` extra installs channels-redis (needed for multi-process WS
# fan-out in prod). `sentry` extra is small + lets ops opt-in by setting
# SENTRY_DSN in the env.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra realtime --extra sentry

# App source
COPY . .

# Pull pre-built CSS from the node stage
COPY --from=css-builder /app/static/css/app.css ./static/css/app.css

# Compile translations + collect static
RUN uv run python manage.py compilemessages || true
RUN SECRET_KEY=collectstatic-only ALLOWED_HOSTS=* \
    uv run python manage.py collectstatic --noinput

# Non-root user
RUN useradd --create-home --uid 1000 apex && chown -R apex:apex /app
USER apex

# Container hosts inject $PORT — Fly defaults to 8080; Cloud Run/Render
# vary. Default to 8080 for clarity in local docker run.
ENV PORT=8080
EXPOSE 8080

# Healthcheck — /__health/ returns JSON; 200 = stack alive.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/__health/ || exit 1

# Daphne ASGI — required for the /ws/ WebSocket consumers (Channels).
# `--proxy-headers` reads X-Forwarded-Proto / X-Forwarded-For so Django
# sees the real client IP + scheme behind a load balancer (Fly Edge,
# Render, nginx, Cloudflare).
# Migrate runs at boot — idempotent + fast when no pending migrations.
CMD ["sh", "-c", "uv run python manage.py migrate --no-input && exec uv run daphne -b 0.0.0.0 -p ${PORT} --proxy-headers --access-log - apex.asgi:application"]
