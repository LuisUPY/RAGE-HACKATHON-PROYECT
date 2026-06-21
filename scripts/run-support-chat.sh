#!/usr/bin/env bash
# Chat de soporte — pide API keys al iniciar (no requiere .env).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec uv run rage-chat-support "$@"
