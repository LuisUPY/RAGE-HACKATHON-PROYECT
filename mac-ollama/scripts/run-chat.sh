#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_load-env.sh"

MODEL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo "RAGE Chat (Ollama local)"
if [[ -n "$MODEL" ]]; then
  uv run rage-chat --model "$MODEL"
else
  uv run rage-chat
fi
