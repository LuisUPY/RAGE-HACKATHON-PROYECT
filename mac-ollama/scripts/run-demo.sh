#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_load-env.sh"
echo "RAGE Demo (offline, sin LLM)"
uv run rage-demo --no-plot
