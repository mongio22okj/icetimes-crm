.PHONY: help setup install css migrate seed run test e2e build collect compile reseed clean docker docker-build docker-up docker-down docker-logs

UV := uv
PY := $(UV) run python

help:
	@echo "Apex Dashboard — make targets"
	@echo ""
	@echo "  make setup          One-time: install deps, build CSS, migrate, seed, compile messages"
	@echo "  make run            Start the Django dev server"
	@echo ""
	@echo "  make install        Install Python + Node deps"
	@echo "  make css            Build the Tailwind CSS bundle"
	@echo "  make migrate        Apply migrations"
	@echo "  make seed           Seed demo data (idempotent — re-runnable)"
	@echo "  make reseed         Drop the SQLite DB + media + reseed from scratch"
	@echo "  make compile        Compile gettext .po → .mo"
	@echo ""
	@echo "  make test           Run unit tests"
	@echo "  make e2e            Run Playwright E2E tests (requires installed browsers)"
	@echo ""
	@echo "  make build          Production CSS + collectstatic"
	@echo "  make collect        Collect static files"
	@echo ""
	@echo "  make docker         Build + run via docker compose"
	@echo "  make docker-build   Build the image"
	@echo "  make docker-up      Up the stack (Postgres + web)"
	@echo "  make docker-down    Stop the stack"
	@echo "  make docker-logs    Tail the web service logs"
	@echo ""
	@echo "  make clean          Remove build artifacts (DB, media, staticfiles, node_modules)"

# ---- One-shot setup ---------------------------------------------------------

setup: install css migrate seed compile
	@echo ""
	@echo "✓ Setup complete. Run: make run"
	@echo "  Then sign in at http://localhost:8000/ with demo / demo1234"

# ---- Dev workflow -----------------------------------------------------------

install:
	$(UV) sync --all-groups
	npm install

css:
	npm run build

migrate:
	$(PY) manage.py migrate

seed:
	$(PY) manage.py seed_demo

reseed:
	rm -f db.sqlite3
	rm -rf media user_files
	$(PY) manage.py migrate
	$(PY) manage.py seed_demo

compile:
	$(PY) manage.py compilemessages || true

run:
	$(PY) manage.py runserver

# ---- Tests ------------------------------------------------------------------

test:
	$(UV) run pytest apps/

e2e:
	$(UV) run pytest tests/e2e/ -m e2e

# ---- Production build -------------------------------------------------------

build: css collect

collect:
	$(PY) manage.py collectstatic --noinput

# ---- Docker -----------------------------------------------------------------

docker: docker-build docker-up

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f web

# ---- Clean ------------------------------------------------------------------

clean:
	rm -f db.sqlite3
	rm -rf media user_files staticfiles node_modules .venv .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned. Run 'make setup' to start fresh."
