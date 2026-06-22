#!/usr/bin/env bash
# Demo RAGE — juez LLM con API key interactiva (~33 escenarios).
#
# Uso:
#   ./scripts/run-demo.sh                    # todos los casos + juez
#   ./scripts/run-demo.sh --core --verbose   # 14 multi-turno
#   ./scripts/run-demo.sh --offline --no-plot  # rápido sin API key
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet
exec uv run rage-demo "$@"
