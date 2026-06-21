#!/usr/bin/env bash
# Load a mac-ollama profile and cd to repo root.
# Usage: source _load-profile.sh [profile_name]
#   profile_name defaults to m1-8gb (e.g. qwen2-7b)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PROFILE_NAME="${1:-m1-8gb}"
PROFILE="${REPO_ROOT}/mac-ollama/profiles/${PROFILE_NAME}.env"
if [[ ! -f "$PROFILE" ]]; then
  echo "ERROR: profile not found: $PROFILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$PROFILE"
set +a
