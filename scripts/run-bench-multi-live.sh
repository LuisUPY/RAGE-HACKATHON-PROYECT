#!/usr/bin/env bash
# Multi-turn benchmark en vivo — pide API key al iniciar (no usa .env).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet
exec uv run rage-bench --multi-turn "$@"
