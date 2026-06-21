#!/usr/bin/env bash
# Load Mac M1 preset and cd to repo root.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PROFILE="${REPO_ROOT}/mac-ollama/profiles/m1-8gb.env"
if [[ ! -f "$PROFILE" ]]; then
  echo "ERROR: profile not found: $PROFILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$PROFILE"
set +a
