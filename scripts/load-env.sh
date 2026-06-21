#!/usr/bin/env bash
# Carga .env sin usar 'source' (por si el usuario no quiere bash source).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  return 0 2>/dev/null || exit 0
fi

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line#"${line%%[![:space:]]*}"}"
  [[ -z "$line" || "$line" == \#* ]] && continue
  [[ "$line" == export\ * ]] && line="${line#export }"
  [[ "$line" != *=* ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  key="${key%"${key##*[![:space:]]}"}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  export "$key=$value"
done < "$ENV_FILE"

# Una clave maestra → asistente + juez
if [[ -n "${RAGE_NVIDIA_API_KEY:-}" && "$RAGE_NVIDIA_API_KEY" != *PEGAR_AQUI* ]]; then
  export RAGE_LLM_API_KEY="${RAGE_LLM_API_KEY:-$RAGE_NVIDIA_API_KEY}"
  export RAGE_JUDGE_API_KEY="${RAGE_JUDGE_API_KEY:-$RAGE_NVIDIA_API_KEY}"
fi

export RAGE_USE_LLM_JUDGE="${RAGE_USE_LLM_JUDGE:-1}"
