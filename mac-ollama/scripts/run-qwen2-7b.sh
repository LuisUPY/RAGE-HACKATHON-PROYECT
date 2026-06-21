#!/usr/bin/env bash
# RAGE + Ollama usando UN solo modelo: qwen2:7b (sin descargar 3b/phi3).
#
# Uso:
#   ./mac-ollama/scripts/run-qwen2-7b.sh              # chat interactivo
#   ./mac-ollama/scripts/run-qwen2-7b.sh chat
#   ./mac-ollama/scripts/run-qwen2-7b.sh redteam --severity high --iterations 5
#   ./mac-ollama/scripts/run-qwen2-7b.sh redteam --unlimited --severity critical
#   ./mac-ollama/scripts/run-qwen2-7b.sh demo
#   ./mac-ollama/scripts/run-qwen2-7b.sh training
#   ./mac-ollama/scripts/run-qwen2-7b.sh test-ollama   # solo probar Ollama, sin RAGE
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_load-profile.sh" qwen2-7b
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_ollama-ensure-model.sh"

MODEL="${OLLAMA_MODEL:-qwen2:7b}"
MODE="${1:-chat}"
shift || true

ensure_ollama_model "$MODEL"

case "$MODE" in
  chat)
    echo "RAGE Chat — modelo único: $MODEL"
    uv run rage-chat --model "$MODEL"
    ;;
  redteam)
    SEVERITY="medium"
    ITERATIONS=10
    UNLIMITED=0
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --severity) SEVERITY="$2"; shift 2 ;;
        --iterations) ITERATIONS="$2"; shift 2 ;;
        --unlimited) UNLIMITED=1; shift ;;
        *) shift ;;
      esac
    done
    echo "RAGE Red-Team — modelo único: $MODEL"
    args=(--no-interactive --model ollama --severity "$SEVERITY"
          --objectives exfil ddl schema_dump canary privilege)
    if [[ "$UNLIMITED" -eq 1 ]]; then
      args+=(--unlimited)
    else
      args+=(--iterations "$ITERATIONS")
    fi
    uv run rage-redteam "${args[@]}"
    ;;
  demo)
    echo "RAGE Demo (offline, sin LLM)"
    uv run rage-demo --no-plot
    ;;
  training)
    echo "RAGE Training-Center (offline, sin LLM)"
    uv run rage-training "$@"
    ;;
  test-ollama)
    echo "Prueba directa Ollama — $MODEL"
    ollama run "$MODEL" "Responde en una sola linea: Ollama OK con qwen2 7b"
    ;;
  *)
    echo "Modo desconocido: $MODE" >&2
    echo "Modos: chat | redteam | demo | training | test-ollama" >&2
    exit 1
    ;;
esac
