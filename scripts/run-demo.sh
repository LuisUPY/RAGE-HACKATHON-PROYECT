#!/usr/bin/env bash
# Demo principal RAGE — offline, sin API key (~5s).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv sync --quiet
exec uv run rage-demo "$@"
