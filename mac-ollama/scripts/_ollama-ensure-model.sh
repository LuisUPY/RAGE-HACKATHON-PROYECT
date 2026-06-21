#!/usr/bin/env bash
# Ensure an Ollama model is available; pull only if missing.
ensure_ollama_model() {
  local model="$1"
  if ! command -v ollama >/dev/null 2>&1; then
    echo "ERROR: ollama no encontrado. Instala desde https://ollama.com" >&2
    return 1
  fi
  if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$model"; then
    echo "[OK] Modelo ya instalado: $model (sin descarga)"
    return 0
  fi
  echo "Modelo no encontrado — descargando solo: $model"
  ollama pull "$model"
}
