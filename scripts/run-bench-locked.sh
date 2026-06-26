#!/usr/bin/env bash
# Official frozen security holdout (eval_locked_v1) — metrics computed at runtime.
#
# Por defecto: --combined --batch --fast  (~1s, L1+L2, sin API key)
# Con juez LLM: añade --full
#
# Uso:
#   ./scripts/run-bench-locked.sh
#   ./scripts/run-bench-locked.sh --full
#   ./scripts/run-bench-locked.sh --filter fn
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

MODE=(--eval-set locked_v1 --combined --batch)
if [[ "$FULL" == true ]]; then
  MODE+=()
else
  MODE+=(--fast)
fi

echo ""
echo "══════════════════════════════════════════════════════════════"
if [[ "$FULL" == true ]]; then
  echo "  LOCKED v1 — L1+L2+Juez (pide API key)"
else
  echo "  LOCKED v1 — L1+L2 (frozen holdout, sin API key)"
fi
echo "══════════════════════════════════════════════════════════════"
echo ""

uv run rage-bench "${MODE[@]}" "${BENCH_ARGS[@]}"

echo ""
if [[ "$FULL" == false ]]; then
  echo "Tip: --full activa el juez LLM en casos borderline."
fi
echo "Tip: --filter fn muestra solo ataques no detectados (FN)."
echo "Regression baseline: benchmarks/baseline_locked_v1.json"
