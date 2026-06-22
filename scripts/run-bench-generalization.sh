#!/usr/bin/env bash
# Benchmark generalization (~80% recall) — optimizado para uso diario.
#
# Por defecto: --combined --batch --fast  (~2s, L1+L2, sin API key)
# Con juez LLM: añade --full            (~15-30s, una sola API key)
#
# Uso:
#   ./scripts/run-bench-generalization.sh
#   ./scripts/run-bench-generalization.sh --full
#   ./scripts/run-bench-generalization.sh --filter fn
#   ./scripts/run-bench-generalization.sh --full --filter fn
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet

FULL=false
BENCH_ARGS=()
for arg in "$@"; do
  if [[ "$arg" == "--full" ]]; then
    FULL=true
  else
    BENCH_ARGS+=("$arg")
  fi
done

MODE=(--eval-set generalization --combined --batch)
if [[ "$FULL" == true ]]; then
  MODE+=()   # juez ON (optimizado: skip L1/L2 confirmados)
else
  MODE+=(--fast)
fi

# --batch implícito en combined; pasar --filter etc.
HAS_BATCH=true
for arg in "${BENCH_ARGS[@]}"; do
  [[ "$arg" == "--batch" ]] && HAS_BATCH=true
done

echo ""
echo "══════════════════════════════════════════════════════════════"
if [[ "$FULL" == true ]]; then
  echo "  GENERALIZATION — L1+L2+Juez (optimizado, pide API key)"
else
  echo "  GENERALIZATION — L1+L2 rápido (~2s, sin API key)"
fi
echo "══════════════════════════════════════════════════════════════"
echo ""

uv run rage-bench "${MODE[@]}" "${BENCH_ARGS[@]}"

if [[ "$HAS_BATCH" == true ]]; then
  echo ""
  if [[ "$FULL" == false ]]; then
    echo "Tip: --full activa el juez LLM en casos borderline (~15-30s)."
  fi
  echo "Tip: --filter fn muestra solo ataques no detectados (FN ~20%)."
fi
