#!/usr/bin/env bash
# Chatbot adaptable por perfil — RAGE detecta, juez de sesión decide (multi-turno).
#
# Uso:
#   ./scripts/run-profile-chat.sh --profile restaurant --offline
#   ./scripts/run-profile-chat.sh --profile support
#   ./scripts/run-profile-chat.sh --list-profiles
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "NOTE: run-profile-chat.sh is deprecated — use ./scripts/run-product-demo.sh" >&2
uv sync --quiet
exec uv run rage-chat-profile "$@"
