#!/usr/bin/env bash
# Benchmark en vivo con juez LLM — pide API key al iniciar (no usa .env).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet
exec uv run rage-bench "$@"
