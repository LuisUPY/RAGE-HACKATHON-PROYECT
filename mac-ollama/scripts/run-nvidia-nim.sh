#!/usr/bin/env bash
# RAGE Chat con NVIDIA NIM
#   Asistente : meta/llama-3.3-70b-instruct     (NVIDIA_API_KEY)
#   Juez L3   : nvidia/llama-3.1-nemotron-nano-8b-v1  (NVIDIA_JUDGE_API_KEY)
#
# Uso:
#   export NVIDIA_API_KEY=nvapi-...          # clave para el asistente
#   export NVIDIA_JUDGE_API_KEY=nvapi-...    # clave para el juez (puede ser la misma)
#   ./mac-ollama/scripts/run-nvidia-nim.sh
#   ./mac-ollama/scripts/run-nvidia-nim.sh redteam
#   ./mac-ollama/scripts/run-nvidia-nim.sh training
#
# Si usas una sola clave para ambos modelos:
#   export NVIDIA_API_KEY=nvapi-...
#   export NVIDIA_JUDGE_API_KEY=$NVIDIA_API_KEY
#   ./mac-ollama/scripts/run-nvidia-nim.sh
#
# Claves gratis en: https://build.nvidia.com (NVIDIA Developer Program)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$REPO_ROOT"

# 1. Verificar clave del asistente principal
if [[ -z "${NVIDIA_API_KEY:-}" ]]; then
  echo ""
  echo "ERROR: NVIDIA_API_KEY no está definida (asistente principal)." >&2
  echo "" >&2
  echo "  Pasos:" >&2
  echo "    1. Crea cuenta gratis en https://build.nvidia.com" >&2
  echo "    2. Genera tu clave desde el dashboard -> 'Get API Key'" >&2
  echo "    3. export NVIDIA_API_KEY=nvapi-..." >&2
  echo "    4. export NVIDIA_JUDGE_API_KEY=nvapi-...  (puede ser la misma clave)" >&2
  echo "    5. Vuelve a ejecutar este script." >&2
  echo ""
  exit 1
fi

# 2. Si no se define clave de juez, usar la misma que el asistente
if [[ -z "${NVIDIA_JUDGE_API_KEY:-}" ]]; then
  echo "INFO: NVIDIA_JUDGE_API_KEY no definida — usando NVIDIA_API_KEY para el juez."
  export NVIDIA_JUDGE_API_KEY="${NVIDIA_API_KEY}"
fi

# 3. Cargar perfil NVIDIA NIM (inyecta RAGE_* vars expandiendo las claves)
set -a
# shellcheck disable=SC1090,SC1091
source "${SCRIPT_DIR}/_load-profile.sh" nvidia-nim
set +a

echo ""
echo "============================================================"
echo "  RAGE — NVIDIA NIM"
echo "  Asistente : ${RAGE_LLM_MODEL}"
echo "  Juez L3   : ${RAGE_JUDGE_MODEL}  (activo: ${RAGE_USE_LLM_JUDGE})"
echo "  Endpoint  : ${RAGE_LLM_BASE_URL}"
echo "============================================================"
echo ""

# 4. Routing por subcomando
SUBCOMMAND="${1:-chat}"
shift || true

case "$SUBCOMMAND" in
  chat)
    uv run rage-chat "$@"
    ;;
  redteam)
    uv run rage-redteam "$@"
    ;;
  training)
    uv run rage-training "$@"
    ;;
  demo)
    uv run rage-demo "$@"
    ;;
  *)
    echo "Subcomandos: chat | redteam | training | demo"
    echo "Ejemplo:     $0 chat"
    exit 1
    ;;
esac
