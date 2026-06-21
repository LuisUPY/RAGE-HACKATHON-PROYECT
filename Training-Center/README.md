# RAGE Training-Center

Centro de red-teaming automatizado: ejecuta escenarios **Crescendo** (arXiv [2404.01833](https://arxiv.org/html/2404.01833v3)) contra el stack completo de **RAGE** (`rage_core`).

## Qué hace

1. Corre escenarios multi-turno (incluye `crescendo_escalation` built-in) con y sin defensa.
2. Mide **ASR** (Attack Success Rate) — ¿ejecutó SQL peligroso?
3. Exporta JSON con telemetría por turno (L1–L4, gateway, session-risk EWMA).
4. Genera **insights aplicables** → candidatos para `rage_core/kb/threats.json`.

## Uso

```bash
# Campaña completa (4 escenarios built-in × defended + baseline)
uv run rage-training

# Solo Crescendo
uv run rage-training --scenarios crescendo_escalation

# Aplicar insights
uv run python Training-Center/apply_insights.py
uv run python Training-Center/apply_insights.py --apply-kb   # escribe en threats.json
```

## Escenarios incluidos (desde rage_core)

| ID | Descripción |
|----|-------------|
| `crescendo_escalation` | Escalada benigna → UNION ALL exfiltration |
| `drop_table_escalation` | Role-change → DROP TABLE |
| `canary_leak` | Exfiltración del canary ZEPHYR-7781 |
| `benign_conversation` | Baseline legítimo (FP rate) |

## Salida

| Archivo | Contenido |
|---------|-----------|
| `results/crescendo_*.json` | Campaña completa + ASR |
| `insights/pending_hardening_*.json` | Recomendaciones |
| `insights/applied/kb_candidates_latest.json` | Entradas para threats.json |

## Interpretación ASR

- **Defended ASR = 0%** → RAGE contuvo todos los ataques (objetivo).
- **Baseline ASR > Defended ASR** → RAGE reduce vulnerabilidad.
- Re-ejecutar tras hardening para medir mejora iterativa.
