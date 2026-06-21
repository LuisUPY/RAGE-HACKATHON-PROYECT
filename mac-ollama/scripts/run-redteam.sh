#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_load-env.sh"

SEVERITY="medium"
ITERATIONS=10
UNLIMITED=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --severity) SEVERITY="$2"; shift 2 ;;
    --iterations) ITERATIONS="$2"; shift 2 ;;
    --unlimited) UNLIMITED=1; shift ;;
    *) shift ;;
  esac
done

echo "RAGE Red-Team (headless, modelo ollama)"

args=(
  --no-interactive
  --model ollama
  --severity "$SEVERITY"
  --objectives exfil ddl schema_dump canary privilege
)

if [[ "$UNLIMITED" -eq 1 ]]; then
  args+=(--unlimited)
else
  args+=(--iterations "$ITERATIONS")
fi

uv run rage-redteam "${args[@]}"
