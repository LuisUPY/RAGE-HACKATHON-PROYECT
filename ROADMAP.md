# RAGE — Roadmap y ramas experimentales

## En `main` (producto actual)

| Componente | Estado |
|------------|--------|
| Motor L1–L4 + gateway SQL | ✅ Estable |
| `rage-demo` — escenarios multi-turno + AUC-D | ✅ |
| Track A — `rage-product-demo` (perfiles + dual API) | ✅ |
| Track B — `rage-bench-product` (~20 casos) | ✅ |
| Holdout `eval_generalization` (~80% recall) | ✅ |
| Hot-update de KB en runtime (`ThreatKBRetriever.add_threat`) | ✅ |
| 232 tests + CI (regresión + generalización) | ✅ |
| Submission Global South (PDF) | ✅ |

## No incluido en `main` (ramas `cursor/*`)

Estos módulos aparecen en papers o README históricos pero **no están mergeados** en la rama principal:

| Módulo | Rama de referencia | Notas |
|--------|-------------------|--------|
| `rage_core/training/` + `Training-Center/` | `cursor/rage-v3-93a0` | Campañas Crescendo, `rage-training`, apply-to-KB |
| `windows-ollama/` | `cursor/windows-ollama-setup-93a0` | Ollama en Windows + GPU |
| `mac-ollama/` | `cursor/mac-ollama-setup-93a0` | Ollama en Apple Silicon |

Para endurecer la KB **sin** Training-Center, usa la API de hot-update documentada en [README.md](README.md#add-a-new-threat-at-runtime-hot-update-no-retraining).

## Próximos pasos sugeridos

1. Merge selectivo de Training-Center desde `cursor/rage-v3-93a0`.
2. Job CI de `ruff` en verde (hoy baseline informativo).
3. Benchmark producto en CI (`run-bench-product.sh --offline`).
