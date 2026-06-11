#!/usr/bin/env bash
set -euo pipefail
# Run both unit tests and E2E tests
echo "=== Unit tests ==="
uv run pytest
echo ""
echo "=== E2E tests ==="
uv run pytest -m e2e
