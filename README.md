# RAGE-HACKATHON-PROYECT

**RAGE** (Retrieval-Augmented Governance Engine) — middleware de defensa en capas contra prompt injection (OWASP LLM01) para agentes Text-to-SQL.

## Componentes

| Módulo | Descripción |
|--------|-------------|
| `decision_engine.py` | Track A – DecisionGateway + demo adversarial 3-turnos |
| `Training-Center/` | Red-teaming Crescendo automatizado × RAGE (ASR, insights) |
| `generate_paper.py` | Genera `RAGE-Paper.pdf` |
| `estado-del-arte-deep-research.md` | Estado del arte y posicionamiento |

## Quick start

```bash
# Demo del gateway (offline)
python decision_engine.py

# Campaña Crescendo × RAGE (offline)
python Training-Center/run_campaign.py
python Training-Center/apply_insights.py
```

Ver [Training-Center/README.md](Training-Center/README.md) para red-teaming completo con `--real-llm` y `--adaptive`.
