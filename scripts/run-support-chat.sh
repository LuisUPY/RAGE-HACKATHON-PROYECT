#!/usr/bin/env bash
# Lanza el chat de soporte técnico con juez LLM activo.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Cargar .env automáticamente (sin que tengas que hacer source .env)
# shellcheck disable=SC1091
source "$ROOT/scripts/load-env.sh"

if [[ ! -f "$ROOT/.env" ]]; then
  echo ""
  echo "No tienes archivo .env todavía."
  echo "Ejecuta primero:  ./scripts/setup-env.sh"
  echo "Luego edita .env y pega tu clave en RAGE_NVIDIA_API_KEY=..."
  echo ""
  exit 1
fi

if [[ "${RAGE_NVIDIA_API_KEY:-}" == *PEGAR_AQUI* || -z "${RAGE_LLM_API_KEY:-}" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo ""
    echo "Falta pegar tu API key en .env"
    echo "  1. Abre:  $ROOT/.env"
    echo "  2. Cambia:  RAGE_NVIDIA_API_KEY=PEGAR_AQUI_TU_CLAVE_NVAPI"
    echo "     por:     RAGE_NVIDIA_API_KEY=nvapi-tu-clave-real"
    echo "  3. Vuelve a ejecutar:  ./scripts/run-support-chat.sh"
    echo ""
    exit 1
  fi
fi

export RAGE_USE_LLM_JUDGE="${RAGE_USE_LLM_JUDGE:-1}"

exec uv run rage-chat-support "$@"
