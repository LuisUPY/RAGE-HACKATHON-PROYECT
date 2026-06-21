# RAGE Training-Center

Centro de red-teaming automatizado: escenarios **Crescendo** contra el stack **RAGE** (`rage_core`).

## Setup (después de clonar)

```bash
cd RAGE-HACKATHON-PROYECT
uv sync --extra dev
```

Sin este paso, `uv run rage-training` falla con `Failed to spawn: rage-training`.

## Comandos

```bash
uv run rage-training
uv run rage-training --scenarios crescendo_escalation
uv run rage-training-apply
uv run rage-training-apply --apply-kb
```

Alternativa directa:

```bash
uv run python -m rage_core.training.cli
uv run python -m rage_core.training.apply
```

## Escenarios built-in

| ID | Descripción |
|----|-------------|
| `crescendo_escalation` | Escalada benigna → UNION ALL exfiltration |
| `drop_table_escalation` | Role-change → DROP TABLE |
| `canary_leak` | Exfiltración del canary ZEPHYR-7781 |
| `benign_conversation` | Baseline legítimo (FP rate) |

## Salida

| Archivo | Contenido |
|---------|-----------|
| `Training-Center/results/crescendo_*.json` | ASR + telemetría por turno |
| `Training-Center/insights/pending_hardening_*.json` | Recomendaciones |
| `Training-Center/insights/applied/kb_candidates_latest.json` | Candidatos para `threats.json` |

## Interpretación

- **Defended ASR = 0%** → RAGE contuvo los ataques.
- **Baseline ASR > Defended ASR** → RAGE reduce vulnerabilidad.
- Re-ejecutar tras hardening para medir mejora.
