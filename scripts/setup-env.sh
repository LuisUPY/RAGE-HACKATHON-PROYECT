#!/usr/bin/env bash
# Crea .env con URLs/modelos por defecto (sin API keys — se piden al ejecutar demos en vivo).
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
  echo "  $TARGET"
  echo ""
  echo "Las API keys NO se guardan en .env."
  echo "Al ejecutar un demo en vivo, el programa te las pedirá en pantalla."
  exit 0
fi

cp "$TEMPLATE" "$TARGET"
echo "Creado: $TARGET (solo URLs y modelos — sin claves API)"
echo ""
echo "Para probar con LLM en vivo, ejecuta por ejemplo:"
echo "  ./scripts/run-support-chat.sh"
echo "  ./scripts/run-product-demo.sh"
echo ""
echo "Pega tu clave nvapi- cuando te la pida (solo esa sesión, no se guarda)."
echo "Obtener clave: https://build.nvidia.com → API Keys"
