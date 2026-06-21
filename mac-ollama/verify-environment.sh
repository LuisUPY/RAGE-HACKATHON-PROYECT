#!/usr/bin/env bash
# Verify prerequisites: Ollama, uv, Python, models.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== RAGE Mac + Ollama — verificacion ==="
echo "Repo: $REPO_ROOT"
echo ""

fail=0

arch="$(uname -m)"
echo "[INFO] arquitectura: $arch"
if [[ "$arch" != "arm64" ]]; then
  echo "[WARN] Este kit esta optimizado para Apple Silicon (arm64)"
fi

if command -v git >/dev/null 2>&1; then
  echo "[OK] git"
else
  echo "[WARN] git no encontrado"
fi

if command -v python3 >/dev/null 2>&1; then
  echo "[OK] $(python3 --version)"
else
  echo "[FAIL] python3 no encontrado" >&2
  fail=$((fail + 1))
fi

if command -v uv >/dev/null 2>&1; then
  echo "[OK] uv $(uv --version)"
else
  echo "[FAIL] uv no encontrado" >&2
  fail=$((fail + 1))
fi

if [[ -d "$REPO_ROOT/rage_core" ]]; then
  echo "[OK] rage_core/"
else
  echo "[FAIL] rage_core/ no existe — ejecuta desde la raiz del repo" >&2
  fail=$((fail + 1))
fi

if command -v ollama >/dev/null 2>&1; then
  echo "[OK] ollama $(ollama --version 2>&1 | head -1)"
else
  echo "[FAIL] ollama no encontrado — instala desde https://ollama.com" >&2
  fail=$((fail + 1))
fi

if curl -sf --max-time 5 http://localhost:11434/api/tags >/dev/null 2>&1; then
  models="$(curl -sf http://localhost:11434/api/tags | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(', '.join(m.get('name','') for m in data.get('models', [])) or '(ninguno)')
" 2>/dev/null || echo "?")"
  echo "[OK] Ollama API — modelos: $models"
else
  echo "[FAIL] Ollama API no responde en localhost:11434" >&2
  echo "       Abre la app Ollama e intenta de nuevo." >&2
  fail=$((fail + 1))
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
  ram_bytes="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
  ram_gb=$((ram_bytes / 1024 / 1024 / 1024))
  echo "[INFO] RAM del sistema: ~${ram_gb} GB"
  if [[ "$ram_gb" -le 8 ]]; then
    echo "[INFO] 8 GB detectados — usa modelos 3B (preset m1-8gb.env)"
  fi
fi

if uv run python -c "from rage_core.layers.layer4_decision import DefensePipeline; print('import_ok')" 2>/dev/null | grep -q import_ok; then
  echo "[OK] rage_core importable"
else
  echo "[FAIL] uv run python no pudo importar rage_core" >&2
  fail=$((fail + 1))
fi

echo ""
if [[ $fail -eq 0 ]]; then
  echo "Verificacion OK. Puedes ejecutar:"
  echo "  ./mac-ollama/scripts/run-demo.sh"
  echo "  ./mac-ollama/scripts/run-chat.sh"
  exit 0
else
  echo "Verificacion fallida ($fail errores)." >&2
  exit 1
fi
