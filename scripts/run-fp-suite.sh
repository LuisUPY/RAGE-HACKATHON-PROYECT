#!/usr/bin/env bash
# Run fp_suite — v2 benign corpus must never get CONTAIN.
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --quiet
uv run pytest tests/fp_suite/ -q "$@"
