#!/usr/bin/env bash
# Track B product benchmark — ChatGate + BotProfile (~20 cases).
#
# Uso:
#   ./scripts/run-bench-product.sh --offline --batch
#   ./scripts/run-bench-product.sh --live --output results/product_run.json --csv results/product_run.csv
#   uv run python scripts/analyze_bench.py results/product_run.json
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet
exec uv run rage-bench-product "$@"
