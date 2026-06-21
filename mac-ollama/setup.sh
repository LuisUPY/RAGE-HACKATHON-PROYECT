#!/usr/bin/env bash
# Full setup for RAGE + Ollama on Mac Apple Silicon (8 GB RAM).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SKIP_MODEL_PULL=0
for arg in "$@"; do
  case "$arg" in
    --skip-model-pull) SKIP_MODEL_PULL=1 ;;
  esac
done

echo "=== RAGE Mac + Ollama — setup ==="
echo "Repo: $REPO_ROOT"
echo ""

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "WARN: Este script esta pensado para macOS."
fi

# 1. Install uv if missing
if ! command -v uv >/dev/null 2>&1; then
  echo "Instalando uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

# 2. Verify Ollama
if ! command -v ollama >/dev/null 2>&1; then
  echo "ERROR: Ollama no instalado. Descarga desde https://ollama.com" >&2
  exit 1
fi

echo "Esperando API de Ollama..."
ready=0
for _ in $(seq 1 30); do
  if curl -sf --max-time 2 http://localhost:11434/api/tags >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
if [[ "$ready" -eq 0 ]]; then
  echo "WARN: Ollama API no responde. Abre la app Ollama e ejecuta setup de nuevo."
fi

# 3. Python deps
echo "Instalando dependencias (uv sync --extra openai)..."
uv sync --extra openai

# 4. Copy .env if missing
env_example="${REPO_ROOT}/mac-ollama/.env.example"
env_file="${REPO_ROOT}/.env"
if [[ ! -f "$env_file" ]]; then
  cp "$env_example" "$env_file"
  echo "Creado .env desde mac-ollama/.env.example"
else
  echo ".env ya existe — no sobrescrito"
fi

# 5. Pull models
if [[ "$SKIP_MODEL_PULL" -eq 0 ]]; then
  models_json="${REPO_ROOT}/mac-ollama/config/models.json"
  while IFS= read -r model; do
    [[ -z "$model" ]] && continue
    echo "Descargando modelo: $model ..."
    ollama pull "$model"
  done < <(python3 -c "
import json
from pathlib import Path
data = json.loads(Path('$models_json').read_text())
for m in data.get('pull_order', []):
    print(m)
")
else
  echo "Skip model pull (--skip-model-pull)"
fi

# 6. Verify
echo ""
"${REPO_ROOT}/mac-ollama/verify-environment.sh"

# 7. Warm-up demo
echo ""
echo "Warm-up: rage-demo (escenario benigno)..."
uv run rage-demo --scenario benign_conversation --no-plot

echo ""
echo "Setup completo."
echo "Siguiente paso: ./mac-ollama/scripts/run-chat.sh"
