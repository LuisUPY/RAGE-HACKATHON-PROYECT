#!/usr/bin/env bash
# Track A product demo — dual API wizard + RAGE gate + per-turn latency.
#
# Uso:
#   ./scripts/run-product-demo.sh
#   ./scripts/run-product-demo.sh --profile support
#   ./scripts/run-product-demo.sh --profile practice --offline
#   ./scripts/run-product-demo.sh --list-profiles
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet
exec uv run rage-product-demo "$@"
