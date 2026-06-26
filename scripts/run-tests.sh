#!/usr/bin/env bash
# Suite de regresión automatizada — NO es la métrica de detección de ataques.
# La evaluación de seguridad oficial está en run-bench-locked.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  RAGE — regresión automatizada (pytest)"
echo "  Verifica contratos de código; NO implica 100% recall en ataques."
echo "  Seguridad open-world: ./scripts/run-bench-locked.sh"
echo "══════════════════════════════════════════════════════════════"
echo ""

uv run pytest tests/ -v --tb=short "$@"
