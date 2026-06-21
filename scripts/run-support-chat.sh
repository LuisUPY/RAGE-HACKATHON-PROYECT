#!/usr/bin/env bash
# Lanza el chat de soporte técnico con juez LLM activo.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi

export RAGE_USE_LLM_JUDGE="${RAGE_USE_LLM_JUDGE:-1}"

exec uv run rage-chat-support "$@"
