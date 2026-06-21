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

## Comandos Training-Center

```bash
uv run rage-training
uv run rage-training --scenarios crescendo_escalation
uv run rage-training-apply
uv run rage-training-apply --apply-kb
```

## Adaptive Red-Teamer (rage-redteam)

```bash
# Modo interactivo (menu curses: configurar escala, objetivos, modelo)
uv run rage-redteam

# Modo headless
uv run rage-redteam --no-interactive --scale light
uv run rage-redteam --no-interactive --objectives exfil ddl --iterations 20 --auto-patch
uv run rage-redteam --no-interactive --model gpt-4o-mini --scale heavy --auto-patch
```

### Escalas predefinidas

| Escala | Iteraciones | Turnos/iter |
|--------|-------------|-------------|
| `light` | 5 | 8 |
| `medio` | 20 | 12 |
| `heavy` | 50 | 20 |

### Teclas durante la ejecucion (modo interactivo)

| Tecla | Accion |
|-------|--------|
| `S` / `Q` | Stop limpio |
| `P` | Pause / Resume entre iteraciones |
| `M` | Cambiar modelo LLM en caliente |
| `V` | Ver tabla de vulnerabilidades |

### Outputs

| Archivo | Contenido |
|---------|-----------|
| `Training-Center/results/redteam_*.json` | Telemetria completa |
| `Training-Center/vulnerabilities/vuln_db.json` | Vulnerabilidades encontradas |
| `rage_core/kb/threats.json` | KB enriquecido por patches |

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
