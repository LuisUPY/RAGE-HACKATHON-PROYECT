#!/usr/bin/env bash
# RAGE Chat con NVIDIA NIM — Llama 3.3 70B (asistente) + Nemotron Nano 8B (juez)
#
# Uso:
#   export NVIDIA_API_KEY=nvapi-...
#   ./mac-ollama/scripts/run-nvidia-nim.sh
#   ./mac-ollama/scripts/run-nvidia-nim.sh redteam
#   ./mac-ollama/scripts/run-nvidia-nim.sh training
#
# La clave se genera gratis en: https://build.nvidia.com (NVIDIA Developer Program)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$REPO_ROOT"

# 1. Verificar clave NVIDIA
if [[ -z "${NVIDIA_API_KEY:-}" ]]; then
  echo "ERROR: NVIDIA_API_KEY no está definida." >&2
  echo "" >&2
  echo "  1. Crea una cuenta gratis en https://build.nvidia.com" >&2
  echo "  2. Genera tu clave desde el dashboard (nvapi-...)" >&2
  echo "  3. Ejecuta:  export NVIDIA_API_KEY=nvapi-..." >&2
  echo "  4. Vuelve a lanzar este script." >&2
  exit 1
fi

# 2. Cargar perfil NVIDIA NIM (inyecta las vars en el entorno actual)
# shellcheck disable=SC1090
set -a
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_load-profile.sh" nvidia-nim
set +a

echo "============================================================"
echo "  RAGE Chat — NVIDIA NIM"
echo "  Asistente : ${RAGE_LLM_MODEL}"
echo "  Juez L3   : ${RAGE_JUDGE_MODEL}"
echo "  Juez activo: ${RAGE_USE_LLM_JUDGE}"
echo "============================================================"
echo ""

# 3. Routing por subcomando
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
    echo "Subcomandos disponibles: chat | redteam | training | demo"
    echo "Ejemplo: $0 chat"
    exit 1
    ;;
esac
