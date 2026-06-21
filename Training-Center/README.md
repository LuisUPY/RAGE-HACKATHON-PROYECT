# RAGE Training-Center

Centro de red-teaming automatizado: escenarios **Crescendo** contra el stack **RAGE** (`rage_core`).

## Setup (después de clonar)

```bash
cd RAGE-HACKATHON-PROYECT
git pull origin main

# Verifica que estás en la RAÍZ del repo (no una subcarpeta anidada):
ls rage_core pyproject.toml
# ↑ si falla, haz: cd ..  hasta encontrar rage_core/

uv sync
uv run rage-training
```

### Errores comunes

| Error | Causa | Solución |
|-------|--------|----------|
| `Extra 'dev' is not defined` | `pyproject.toml` viejo o carpeta incorrecta | `git pull` + usar solo `uv sync` (sin `--extra dev`) |
| `Resolved 2 packages` | No estás en el repo completo | `cd` a la carpeta que contiene `rage_core/` |
| `No module named 'rage_core'` | No corriste `uv sync` o carpeta incorrecta | Desde raíz: `uv sync` luego `uv run rage-training` |

## Comandos

```bash
uv run rage-training
uv run rage-training --scenarios crescendo_escalation
uv run rage-training-apply
uv run rage-training-apply --apply-kb
```

Alternativa:

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
