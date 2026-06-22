#!/usr/bin/env bash
# Benchmark en vivo con juez LLM — vista estilo chat (pide API keys al iniciar).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet
exec uv run rage-bench "$@"
