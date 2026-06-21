# RAGE Training-Center

Centro de red-teaming automatizado que adapta el ataque **Crescendo** (Russinovich et al., [arXiv 2404.01833](https://arxiv.org/html/2404.01833v3)) al dominio **Text-to-SQL** de RAGE.

Ejecuta campañas multi-turno benignas contra el `DecisionGateway`, mide **ASR** (Attack Success Rate), detecta bypasses del gateway y exporta insights aplicables al hardening.

## Estructura

```
Training-Center/
├── run_campaign.py          # CLI principal – lanza campaña Crescendo × RAGE
├── apply_insights.py        # Aplica resultados → patrones KB / reporte
├── crescendo/                 # Motor de orquestación
│   ├── scenarios.py           # Carga escenarios JSON
│   ├── attack_generator.py    # Turnos scripted + adaptive (Crescendomation-style)
│   ├── judge.py               # Judge + Refusal detection
│   ├── orchestrator.py        # Loop multi-turno con backtracking
│   ├── campaign.py            # Batch runner + agregación ASR
│   ├── reporter.py            # Export JSON + insights
│   ├── gateway_factory.py     # RAGE gateway vs baseline passthrough
│   └── simulated_agent.py     # Agente vulnerable offline (sin API key)
├── scenarios/                 # Escenarios Text-to-SQL Crescendo
│   ├── text2sql_exfil.json
│   ├── text2sql_ddl.json
│   ├── text2sql_schema_dump.json
│   └── text2sql_union_exfil.json
├── results/                   # Salida: crescendo_YYYYMMDD_HHMMSS.json
└── insights/                  # pending_hardening_*.json + applied/
```

## Uso rápido (offline, sin API key)

```bash
python Training-Center/run_campaign.py
python Training-Center/apply_insights.py
```

Modo offline usa `SimulatedCrescendoAgent` (agente vulnerable simulado) para demostrar el flujo completo y generar métricas.

## Uso con LLM real

```bash
export OPENAI_API_KEY=sk-...
python Training-Center/run_campaign.py --real-llm --llm-judge
python Training-Center/run_campaign.py --real-llm --adaptive --iterations 3
```

| Flag | Descripción |
|------|-------------|
| `--scenarios text2sql_exfil text2sql_ddl` | Subconjunto de escenarios |
| `--iterations N` | Repeticiones independientes (paper: 10) |
| `--real-llm` | Target = `PrincipalAgent` con gpt-4o |
| `--adaptive` | Generador de turnos estilo Crescendomation |
| `--llm-judge` | Judge semántico para evaluar éxito |
| `--no-baseline` | Omitir runs sin gateway (solo RAGE) |

## Salida de resultados

### `results/crescendo_*.json`

Contiene por cada run:

- `success`, `success_turn`, `gateway_bypassed`
- Telemetría por turno: `gateway_score`, `gateway_action`, `vulnerabilities`
- `summary.attack_success_rate`, `summary.gateway_bypass_rate`
- Comparación baseline vs gateway en `actionable_insights.metrics`

### `insights/pending_hardening_*.json`

Recomendaciones para aplicar:

- `recommended_kb_patterns` – regex Crescendo para InputFilter/RAG KB
- `low_score_bypasses` – turnos que pasaron con score ≤ 2
- `recommended_threshold_adjustments`

### Aplicar insights

```bash
python Training-Center/apply_insights.py --campaign crescendo_20250621_120000
```

Genera:

- `insights/applied/threat_patterns_latest.json`
- `insights/applied/hardening_report_*.md`

## Flujo de ensayo y error

1. **Baseline** – `run_campaign.py` ejecuta cada escenario con y sin RAGE.
2. **Medir** – ASR, bypass rate, turnos hasta éxito.
3. **Analizar** – `apply_insights.py` extrae patrones de bypass.
4. **Endurecer** – Añadir patrones a `InputFilter.THREAT_PATTERNS` en `decision_engine.py`.
5. **Re-ejecutar** – Comparar ASR entre campañas en `results/`.

## Referencia Crescendo

El ataque explota escalada benigna multi-turno (*foot-in-the-door*): turnos 1–N no contienen payloads obvios (DAN, `###SYSTEM###`), sino referencias al output previo del modelo. Por eso el demo de 3 turnos en `decision_engine.py` no cubre este vector — Training-Center sí.

Implementación inspirada en **Crescendomation** (PyRIT): backtracking en rechazos, judge de éxito, generación adaptativa opcional.
