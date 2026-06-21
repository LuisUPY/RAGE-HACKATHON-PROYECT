#!/usr/bin/env bash
# Verifica que el clone de RAGE esté completo antes de uv sync / rage-training.
set -euo pipefail

echo "=== RAGE setup check ==="
echo "Directorio actual: $(pwd)"
echo ""

fail=0

if [[ ! -f pyproject.toml ]]; then
  echo "❌ No hay pyproject.toml aquí."
  fail=1
else
  name=$(grep -E '^name\s*=' pyproject.toml | head -1 || true)
  echo "✓ pyproject.toml ($name)"
  if ! grep -q 'rage-multiturn' pyproject.toml 2>/dev/null; then
    echo "❌ pyproject.toml no es del proyecto RAGE actual (debe decir rage-multiturn)."
    fail=1
  fi
fi

if [[ ! -d rage_core ]]; then
  echo "❌ No existe rage_core/ en este directorio."
  echo ""
  echo "   Causas habituales:"
  echo "   1. Estás en una subcarpeta (ej. RAGE-HACKATHON-PROYECT/RAGE-HACKATHON-PROYECT/)"
  echo "   2. Clone viejo o fork desactualizado"
  echo "   3. Descargaste solo Training-Center, no el repo completo"
  echo ""
  echo "   Busca rage_core en el árbol:"
  found=$(find . -maxdepth 4 -type d -name rage_core 2>/dev/null | head -3 || true)
  if [[ -n "$found" ]]; then
    echo "   Encontrado en:"
    echo "$found" | sed 's/^/     /'
    echo "   → cd a la carpeta PADRE de rage_core/ (donde también está pyproject.toml)"
  else
    echo "   No se encontró rage_core en subcarpetas — re-clona el repo:"
    echo "   git clone https://github.com/LuisUPY/RAGE-HACKATHON-PROYECT.git"
  fi
  fail=1
else
  echo "✓ rage_core/ ($(ls rage_core | tr '\n' ' '))"
fi

if [[ ! -d tests ]]; then
  echo "⚠ tests/ no encontrado (opcional pero indica clone incompleto)"
fi

if [[ -d .git ]]; then
  echo ""
  echo "Git remote:"
  git remote -v 2>/dev/null | head -2 || true
  echo "Último commit: $(git log -1 --oneline 2>/dev/null || echo '?')"
else
  echo "⚠ No hay .git — ¿descargaste ZIP parcial?"
  fail=1
fi

echo ""
if [[ $fail -eq 0 ]]; then
  echo "✅ Estructura OK. Siguiente paso:"
  echo "   uv sync"
  echo "   uv run rage-training"
  exit 0
else
  echo "❌ Corrige la ubicación o re-clona antes de continuar."
  exit 1
fi
