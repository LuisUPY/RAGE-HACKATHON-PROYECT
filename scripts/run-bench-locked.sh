#!/usr/bin/env bash
# Official frozen security holdout — RAGE v1 (default) or v2 (--v2).
#
#   ./scripts/run-bench-locked.sh           # v1 L1+L2
#   ./scripts/run-bench-locked.sh --v2        # v2 pipeline
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet

ENGINE=v1
FULL=false
BENCH_ARGS=()
for arg in "$@"; do
  if [[ "$arg" == "--full" ]]; then
    FULL=true
  elif [[ "$arg" == "--v2" ]]; then
    ENGINE=v2
  else
    BENCH_ARGS+=("$arg")
  fi
done

MODE=(--eval-set locked_v1 --combined --batch)
if [[ "$ENGINE" == "v2" ]]; then
  MODE+=(--engine v2)
else
  if [[ "$FULL" == true ]]; then
    :
  else
    MODE+=(--fast)
  fi
fi

echo ""
echo "══════════════════════════════════════════════════════════════"
if [[ "$ENGINE" == "v2" ]]; then
  echo "  LOCKED v1 — RAGE v2 (L0–L4, frozen holdout)"
elif [[ "$FULL" == true ]]; then
  echo "  LOCKED v1 — L1+L2+Juez (pide API key)"
else
  echo "  LOCKED v1 — L1+L2 (frozen holdout, sin API key)"
fi
echo "══════════════════════════════════════════════════════════════"
echo ""

uv run rage-bench "${MODE[@]}" "${BENCH_ARGS[@]}"

echo ""
if [[ "$ENGINE" == "v1" && "$FULL" == false ]]; then
  echo "Tip: --full activa el juez LLM en casos borderline."
fi
if [[ "$ENGINE" == "v2" ]]; then
  echo "Regression baseline: benchmarks/baseline_locked_v2.json"
else
  echo "Regression baseline: benchmarks/baseline_locked_v1.json"
fi
echo "Tip: --filter fn muestra solo ataques no detectados (FN)."
