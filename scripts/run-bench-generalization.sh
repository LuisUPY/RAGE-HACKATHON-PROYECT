#!/usr/bin/env bash
# DEPRECATED — use ./scripts/run-bench-locked.sh (eval_locked_v1 official holdout).
set -euo pipefail
echo "NOTE: run-bench-generalization.sh is deprecated — use ./scripts/run-bench-locked.sh" >&2
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/scripts/run-bench-locked.sh" "$@"
