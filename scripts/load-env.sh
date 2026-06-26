#!/usr/bin/env bash
# Carga .env (solo opciones no secretas; las API keys se piden al ejecutar demos en vivo).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT/.env}"

SECRET_KEYS="RAGE_NVIDIA_API_KEY RAGE_LLM_API_KEY RAGE_JUDGE_API_KEY OPENAI_API_KEY"

_is_secret() {
  local k="$1"
  for s in $SECRET_KEYS; do
    [[ "$k" == "$s" ]] && return 0
  done
  return 1
}

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
  _is_secret "$key" && continue
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  export "$key=$value"
done < "$ENV_FILE"

export RAGE_USE_LLM_JUDGE="${RAGE_USE_LLM_JUDGE:-1}"
