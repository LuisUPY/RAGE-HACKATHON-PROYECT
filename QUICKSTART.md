# RAGE — Guía rápida

Comandos para **actualizar el repo**, **instalar** y **probar** todo lo que está en `main`.

Repositorio: https://github.com/LuisUPY/RAGE-HACKATHON-PROYECT.git

## 1. Actualizar e instalar

```bash
cd ~/RAGE-HACKATHON-PROYECT
git pull origin main
bash scripts/check_setup.sh    # debe decir "Estructura OK"
uv sync
```

## 2. Validación completa (release / hackathon)

```bash
./scripts/validate-all.sh
```

Ejecuta: setup check → 232 tests → benchmark producto → generalización → ablation → PDF.

## 3. Tests

```bash
# Regresión (contratos de código — 232 tests)
./scripts/run-tests.sh

# Equivalente
uv run pytest tests/ -q
```

**Importante:** pasar pytest **no** significa 100% detección de ataques.

## 4. Benchmark de seguridad (métrica honesta)

```bash
./scripts/run-bench-generalization.sh          # ~1s, offline
./scripts/run-bench-generalization.sh --full   # con juez LLM (API key)
```

Recall objetivo **~80%** en holdout fuera de la KB; algunos `FN` son esperados.

## 5. Demo investigación (`rage-demo`)

```bash
# Sin API key
uv run rage-demo --offline --core --no-plot

# Un escenario con detalle
uv run rage-demo --offline --scenario drop_table_escalation --verbose

# Con gráfica AUC
uv run rage-demo --offline --core

# Con juez LLM (API key interactiva)
./scripts/run-demo.sh
```

## 6. Track A — demo de producto (chat por perfil)

```bash
# Sin API key
./scripts/run-product-demo.sh --profile restaurant --offline

# Con dos modelos (asistente + juez)
./scripts/run-product-demo.sh
./scripts/run-product-demo.sh --profile support

./scripts/run-product-demo.sh --list-profiles
```

Docs: [Documentation/PRODUCT_DEMO.md](Documentation/PRODUCT_DEMO.md)

## 7. Track B — benchmark de producto (~20 casos)

```bash
./scripts/run-bench-product.sh --offline --batch
./scripts/run-bench-product.sh --live --output results/product_run.json
uv run python scripts/analyze_bench.py results/product_run.json
```

Docs: [Documentation/PRODUCT_BENCHMARK.md](Documentation/PRODUCT_BENCHMARK.md)

## 8. Chat de soporte IT (requiere API key)

```bash
./scripts/setup-env.sh          # una vez
# Editar .env → RAGE_NVIDIA_API_KEY=nvapi-...
./scripts/run-support-chat.sh
```

## 9. API keys (opcional)

```bash
cp .env.template .env
# Pegar RAGE_NVIDIA_API_KEY o OPENAI_API_KEY
```

Ver `.env.template` para URLs y modelos por defecto (NVIDIA NIM).

## 10. Lint

```bash
uv run ruff check .
```

El repo tiene violaciones de estilo preexistentes; el CI las reporta pero no bloquea el merge.

## 11. Documentación clave

| Archivo | Contenido |
|---------|-----------|
| [README.md](README.md) | Visión general y arquitectura |
| [Documentation/EVALUATION.md](Documentation/EVALUATION.md) | Qué significan los números (leer antes de citar) |
| [tests/README.md](tests/README.md) | Tests vs benchmark de seguridad |
| [ROADMAP.md](ROADMAP.md) | Qué está en main vs ramas experimentales |
| [AGENTS.md](AGENTS.md) | Notas para Cursor Cloud |

## Flujo mínimo diario

```bash
git pull origin main && uv sync && ./scripts/run-tests.sh -q && ./scripts/run-bench-generalization.sh
```
