#!/usr/bin/env bash
# Benchmark generalization (~80%% recall holdout) — pide API key al iniciar.
#
# Uso:
#   ./scripts/run-bench-generalization.sh           # vista chat en vivo
#   ./scripts/run-bench-generalization.sh --batch   # tabla resumida
#   ./scripts/run-bench-generalization.sh --batch --filter fn   # solo FN
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet

EXTRA=("$@")
HAS_BATCH=false
for arg in "${EXTRA[@]}"; do
  [[ "$arg" == "--batch" ]] && HAS_BATCH=true
done

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  GENERALIZATION HOLDOUT — eval-set generalization (~80% recall)"
echo "══════════════════════════════════════════════════════════════"
echo ""

echo "▶ Single-turn (30 casos: 20 ataques + 10 benignos)"
uv run rage-bench --holdout --eval-set generalization "${EXTRA[@]}"

echo ""
echo "▶ Multi-turn (12 escenarios, 16 turnos de ataque)"
uv run rage-bench --multi-turn --eval-set generalization "${EXTRA[@]}"

if [[ "$HAS_BATCH" == true ]]; then
  echo ""
  echo "Tip: --filter fn muestra solo ataques no detectados (FN esperados ~20%)."
fi
