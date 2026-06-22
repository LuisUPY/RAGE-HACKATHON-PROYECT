#!/usr/bin/env bash
# Suite de regresión automatizada — NO es la métrica de detección de ataques.
# La evaluación open-world de seguridad está en run-bench-generalization.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  RAGE — regresión automatizada (pytest)"
echo "  Verifica contratos de código; NO implica 100% recall en ataques."
echo "  Seguridad open-world: ./scripts/run-bench-generalization.sh"
echo "══════════════════════════════════════════════════════════════"
echo ""

uv run pytest tests/ -v --tb=short "$@"
