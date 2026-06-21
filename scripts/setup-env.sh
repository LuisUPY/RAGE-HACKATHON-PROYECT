#!/usr/bin/env bash
# Crea .env desde el lienzo .env.template (no sobrescribe si ya existe).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TEMPLATE="$ROOT/.env.template"
TARGET="$ROOT/.env"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "ERROR: no se encuentra .env.template en $ROOT" >&2
  exit 1
fi

if [[ -f "$TARGET" ]]; then
  echo "Ya existe .env — no lo sobrescribo."
  echo "Edita este archivo y pega tu clave:"
  echo "  $TARGET"
  echo ""
  echo "Busca la línea:"
  echo "  RAGE_NVIDIA_API_KEY=PEGAR_AQUI_TU_CLAVE_NVAPI"
  echo "y sustituye PEGAR_AQUI_TU_CLAVE_NVAPI por tu nvapi-... de build.nvidia.com"
  exit 0
fi

cp "$TEMPLATE" "$TARGET"
echo "Creado: .env"
echo ""
echo "Siguiente paso — abre .env y pega TU clave NVIDIA en UNA sola línea:"
echo ""
echo "  RAGE_NVIDIA_API_KEY=nvapi-tu-clave-real"
echo ""
echo "Obtener clave: https://build.nvidia.com  →  API Keys"
echo ""
echo "Luego ejecuta:"
echo "  ./scripts/run-support-chat.sh"
