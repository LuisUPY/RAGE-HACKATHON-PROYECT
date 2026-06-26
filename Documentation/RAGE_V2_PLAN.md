# RAGE v2 — Plan detallado de reestructuración

**Estado:** Fase 3 completada (benchmark v2 + `baseline_locked_v2.json`); Fase 4–5 pendiente  
**Base de código:** `rage_core` (v1) + PRs pendientes de merge (`honest-benchmarks`, `session-api-keys`, `project-shape`)  
**Objetivo:** defensa multi-turno **precavida pero usable** — cero falsos positivos en benigno (CI), detección fuerte en ataques confirmados, chat no interrumpido salvo alta confianza.

---

## 1. Resumen ejecutivo

### Problema en v1

| Síntoma | Causa raíz en código |
|---------|----------------------|
| Chat “demasiado estricto” | `ChatGate._needs_judge_review` escala por L3 `suspicious` y `policy_would_block` con umbrales multi-turno agresivos (`access_policy.py`) |
| Falsos positivos latentes | L1 con ~250 regex amplias; L2 tiered (0.55–0.70); política multi-turno con L2 hasta 0.28 + drift ≥ 0.65 |
| Dos caminos de veredicto | Benchmark (`is_attack_verdict` / `is_multiturn_attack_verdict`) vs producto (`ChatGate` + `SessionJudge`) con semántica distinta de “bloqueo” |
| L4 desacoplado | Banda allow/warn/block no gobierna el benchmark; pesos en docstring ≠ implementación |
| Calibración opaca | `eval_generalization` ajustado a banda 75–85% recall (legacy) |

### Decisión estratégica (cerrada)

**Refactor incremental en el mismo repositorio**, no repo greenfield separado.

- Motivo: conservar datasets, tests gateway, métricas AUC-D, perfiles de producto y CI existente.
- Paquete nuevo **`rage_core/v2/`** convive con v1 hasta migración completa; CLIs ganan flag `--v2` y luego sustituyen defaults.
- Evaluación oficial: **`eval_locked_v1`** (PR `cursor/honest-benchmarks-6225`) como holdout congelado; nueva suite **`fp_suite`** como gate duro de 0 CONTAIN en benigno.

---

## 2. Decisiones de producto (cerradas)

| Tema | Decisión |
|------|----------|
| UX ante riesgo medio | **ALERT** — aviso suave al usuario; **el chat continúa** |
| Bloqueo de conversación | Solo **CONTAIN** — alta confianza; único punto: **UserGate** |
| Herramientas / SQL | **ToolGateway** separado; bloqueo por política de herramienta ≠ inyección |
| L0 hard match | Único camino a CONTAIN inmediato sin trayectoria (patrones inequívocos, ≤25 reglas) |
| L1 DomainContext | Capa anti-FP; puede **vetar CONTAIN** si el mensaje encaja en el perfil del bot |
| L2 Trajectory | Núcleo multi-turno (sustituye rol de L3 drift + parte de `is_multiturn_attack_verdict`) |
| L3 FamilyHints | Pistas por familia OWASP; peso bajo; **nunca** bloquea solo por similitud RAG |
| L4 Fusion | Emite **CLEAR / WATCH / ALERT / CONTAIN** (no allow/warn/block para producto) |
| Juez LLM | **Fuera del hot path**; solo tras ALERT, sesgo explícito ALLOW; nunca en CI `--fast` |
| API keys | Por sesión en TTY (PR `session-api-keys`); no persistir secretos en disco |
| Legacy `eval_generalization` | `pytest -m dev_eval`; no métrica oficial |

---

## 3. Arquitectura objetivo

```
                    ┌─────────────────────────────────────────┐
  User turn ───────►│ L0 HardSignals   (≤25 reglas críticas)  │
                    └──────────────────┬──────────────────────┘
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │ L1 DomainContext  (perfil + anti-FP)    │
                    └──────────────────┬──────────────────────┘
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │ L2 Trajectory     (estado multi-turno)  │
                    └──────────────────┬──────────────────────┘
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │ L3 FamilyHints    (KB, umbral alto)     │
                    └──────────────────┬──────────────────────┘
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │ L4 Fusion         → Verdict v2            │
                    └──────────┬──────────────┬───────────────┘
                               ▼              ▼
                         UserGate        ToolGateway
                    (chat UX policy)   (SQL / export / tools)
                               │
                               ▼ (solo si ALERT y política lo pide)
                         EscalationJudge (LLM opcional, sesgo ALLOW)
```

### Modelo de veredicto v2

```python
class Verdict(str, Enum):
    CLEAR = "clear"      # sin señal actionable
    WATCH = "watch"      # telemetría / métricas solamente
    ALERT = "alert"      # aviso UX; chat sigue
    CONTAIN = "contain"  # UserGate bloquea turno (o deny en multi-turno confirmado)
```

### UserGate (política UX)

| Verdict L4 | Acción chat | Mensaje usuario |
|------------|-------------|-----------------|
| CLEAR | Responder normal | — |
| WATCH | Responder normal | — (solo logs) |
| ALERT | Responder + banner opcional | “Hemos detectado un patrón inusual…” |
| CONTAIN | **No** llamar al asistente | Mensaje de seguridad estándar |

**Regla:** `L1.veto_contain == True` → downgrade CONTAIN → ALERT (como máximo).

### ToolGateway

- Portar **`rage_core/layers/gateway.py`** casi sin cambios.
- Entrada: `Verdict` + `GatewaySessionContext` + `ToolCallRequest`.
- CONTAIN o hard L0 en turno actual → rechazar herramientas sensibles aunque el texto SQL parezca válido.
- Bloqueos por allowlist SQL **no** cuentan como FP de inyección (mantener tests actuales).

---

## 4. Especificación por capa

### L0 — HardSignals

**Propósito:** señales inequívocas de jailbreak / exfil / destrucción; único bloqueo “duro” sin esperar trayectoria.

| Parámetro | Valor inicial |
|-----------|---------------|
| Tamaño ruleset | ≤ 25 patrones (YAML/JSON externo, no 250 inline) |
| Salida | `hard_hit: bool`, `rule_id`, `family` |
| → L4 | `hard_hit` fuerza piso de score; puede emitir CONTAIN directo si L1 no veta |

**Contenido típico (ejemplos):** “ignore all previous instructions”, `DROP TABLE`, “reveal system prompt”, token/API key exfil explícita.

**No incluir:** frases de negocio (“exportar reporte”, “datos de clientes” en contexto de perfil).

**Migración desde v1:** extraer subconjunto de `layer1_rules.py` con alta precisión; el resto pasa a L3 hints o se elimina.

---

### L1 — DomainContext

**Propósito:** reducir FP alinear el mensaje con `BotProfile` (restaurant, support, reports…).

| Señal | Cómo |
|-------|------|
| `domain_plausible` | Keywords + intents permitidos del perfil + turno dentro de `allowed_topics` |
| `veto_contain` | True si mensaje encaja en uso legítimo documentado del perfil |
| `risk_adjustment` | −15 a −30 puntos en score L4 si plausible |

**Ejemplos veto:** soporte IT pidiendo “exportar logs”; restaurante pidiendo “lista de reservas”.

**Implementación:** nuevo módulo `rage_core/v2/layers/domain_context.py`; datos en `profiles/*.json` ampliados con `benign_intents[]` y `contain_veto_patterns[]`.

---

### L2 — Trajectory

**Propósito:** detectar Crescendo / salami sin castigar un solo turno benigno.

| Señal | Definición |
|-------|------------|
| `turn_embedding` | Unificar con L3 v1: un solo vectorizador (HashingVectorizer 2048, offline) |
| `step_drift` | Distancia coseno turno N vs N−1 |
| `baseline_drift` | Distancia vs turno 0 |
| `trajectory_score` | EWMA de riesgo por turno (α = 0.25, más conservador que v1 0.30) |
| `escalation_detected` | Ver tabla abajo |

**Umbrales iniciales (conservadores — prioridad 0 FP):**

| Condición | Umbral | Veredicto máximo sin L0 |
|-----------|--------|-------------------------|
| Solo drift alto, turn 0–1 | step or baseline > **0.78** | ALERT |
| Turn ≥ 2, drift > **0.72** y L3 hint score > **0.65** | — | ALERT |
| Turn ≥ 3, monotonic escalation (3 turnos subiendo drift) y session_trajectory > **0.55** | — | CONTAIN si no veto L1 |
| Session trajectory EWMA | > **0.65** con L3 hint confirmando | CONTAIN |

**Explícitamente eliminado respecto a v1:** L2 RAG ≥ 0.28 como disparador de ataque multi-turno.

---

### L3 — FamilyHints

**Propósito:** recuperar recall sin FP — solo eleva WATCH/ALERT, raramente CONTAIN.

| Parámetro | Valor |
|-----------|-------|
| Fuente | `kb/threats.json` (TF-IDF o mismo embedder que L2 trajectory) |
| `hint_score` | Similitud coseno top-1 |
| Umbrales | hint ≥ **0.72** → contribuye a ALERT; ≥ **0.82** + trajectory → candidato CONTAIN |
| Solo | Nunca CONTAIN si `hint_score` es la única señal fuerte |

---

### L4 — Fusion

**Propósito:** un solo score 0–100 y veredicto v2.

**Pesos iniciales (documentados = implementados):**

| Fuente | Puntos máx |
|--------|------------|
| L0 hard_hit | +55 |
| L3 hint (alto) | +25 |
| L2 trajectory escalation | +30 |
| L2 drift solo | +15 |
| L1 domain (anti) | −25 si veto |

**Umbrales veredicto:**

| Score | Veredicto |
|-------|-----------|
| 0 – 34 | CLEAR |
| 35 – 54 | WATCH |
| 55 – 74 | ALERT |
| ≥ 75 | CONTAIN (sujeto a veto L1 → ALERT) |

**API única:**

```python
def fuse(signals: LayerSignalsV2, profile: BotProfile) -> FusionResult:
    ...
```

Reemplaza la dupla `access_policy` + banda L4 para **todos** los caminos (bench + producto).

---

### EscalationJudge

- **Trigger:** UserGate recibe ALERT y `profile.escalate_on_alert=True`, o usuario en modo `--full`.
- **Input:** historial recortado, briefing estructurado (sin prompt del sistema completo).
- **Output:** `ALLOW` (default ante duda) | `ESCALATE_TO_CONTAIN`
- **Offline:** reglas mínimas — solo ESCALATE si L0 hard_hit o trajectory ya en candidato CONTAIN.

---

## 5. Mapeo v1 → v2

| v1 | v2 | Acción |
|----|-----|--------|
| `layer1_rules.py` (250) | L0 (25) + L3 hints | Podar y externalizar |
| `layer2_rag.py` | L3 FamilyHints | Subir umbrales; quitar de política multi-turno directa |
| `layer3_semantic.py` | L2 Trajectory | Unificar embedder; renombrar señales |
| `layer4_decision.py` | L4 Fusion | Nuevos veredictos y pesos |
| `access_policy.py` | L4 + tests | **Reescribir** → eliminar archivo |
| `DefensePipeline` | `PipelineV2` | Sin ratchet en bench; ratchet opcional solo demo legacy |
| `ChatGate` | `UserGate` | ALERT no bloquea; CONTAIN sí |
| `SessionJudge` | `EscalationJudge` | Solo post-ALERT |
| `gateway.py` | `ToolGateway` | Port directo |
| `eval_generalization` | dev_eval | No oficial |
| `eval_locked_v1` | oficial | Mantener + ampliar benignos en `fp_suite` |

---

## 6. Estructura de repositorio (objetivo)

```
rage_core/
├── v2/
│   ├── __init__.py
│   ├── models.py              # Verdict, LayerSignalsV2, FusionResult
│   ├── pipeline.py            # PipelineV2
│   ├── layers/
│   │   ├── l0_hard.py
│   │   ├── l1_domain.py
│   │   ├── l2_trajectory.py
│   │   ├── l3_hints.py
│   │   └── l4_fusion.py
│   ├── enforce/
│   │   ├── user_gate.py
│   │   └── tool_gateway.py    # wrap gateway.py
│   ├── judge/
│   │   └── escalation.py
│   └── kb/
│       └── rules/
│           └── l0_hard.yaml
├── layers/                    # v1 (deprecated, quitar en fase 5)
├── gate/
├── benchmark/
│   └── v2_evaluator.py
└── ...

tests/
├── fp_suite/                  # NUEVO — gate CI duro
│   ├── test_benign_restaurant.py
│   ├── test_benign_support.py
│   └── fixtures/benign_turns.json
├── v2/
│   ├── test_fusion.py
│   ├── test_trajectory.py
│   └── test_user_gate.py
└── ... (v1 tests hasta migración)

rage_core/kb/
├── eval_locked_v1/            # oficial (desde PR honest-benchmarks)
└── fp_suite_corpus.json       # turnos benignos ampliados
```

---

## 7. Evaluación y CI

### Gates obligatorios (default CI)

| Gate | Criterio |
|------|----------|
| `fp_suite` | **0 CONTAIN** en corpus benigno (~150+ turnos multi-perfil) |
| `eval_locked_v1` | Snapshot en `benchmarks/baseline_locked_v2.json`; 0 FP; recall documentado sin banda artificial |
| Regresión gateway | Portar `tests/test_gateway.py` |
| UserGate | ALERT permite respuesta; CONTAIN no |

### Métricas reportadas

- **Benign usability:** % turnos CLEAR+WATCH+ALERT (objetivo ≥ 98% en fp_suite)
- **Attack recall:** locked_v1 + escenarios multi-turno etiquetados
- **Product track:** judge override rate (objetivo ↓ vs v1)

### No hacer

- Añadir reglas L0/L1 para subir recall **mirando** locked_v1
- Banda “75–85% recall” en CI
- Casos “FN expected” en dataset oficial

---

## 8. Fases de implementación

### Fase 0 — Preparación (1 PR)

- [ ] Merge a `main`: `honest-benchmarks`, `session-api-keys`, `project-shape`
- [ ] Congelar baseline v1 en tag `v1.0.0-baseline` para comparación A/B
- [ ] Añadir `Documentation/RAGE_V2_PLAN.md` (este documento)

### Fase 1 — Esqueleto v2 + fp_suite (1–2 PR)

- [ ] Crear `rage_core/v2/` con `models.py`, `PipelineV2` stub
- [ ] Corpus `fp_suite` desde perfiles + holdout benigno + frases que hoy disparan L1
- [ ] Tests: `0 CONTAIN` con pipeline stub que siempre CLEAR (baseline vacío)
- [ ] CI job `fp-suite` separado

**Criterio de salida:** fp_suite corre en CI; estructura importable.

### Fase 2 — L4 Fusion + L1 Domain + UserGate (1 PR)

- [ ] Implementar L1 + L4 con umbrales conservadores
- [ ] `UserGate`: ALERT vs CONTAIN
- [ ] Sustituir `ChatGate` en `rage-product-demo --v2 --offline`
- [ ] fp_suite debe pasar con 0 CONTAIN

**Criterio de salida:** demo producto v2 offline usable; fp_suite verde.

### Fase 3 — L0 Hard + L3 Hints (1 PR)

- [ ] Extraer 25 reglas L0 a YAML
- [ ] L3 FamilyHints con umbrales altos
- [ ] Correr `eval_locked_v1`; actualizar baseline v2 si recall aceptable con 0 FP

**Criterio de salida:** locked_v1 ≥ 90% recall, 0 FP, fp_suite verde.

### Fase 4 — L2 Trajectory (1 PR)

- [ ] Portar lógica drift v1 → L2 con umbrales nuevos
- [ ] Eliminar dependencia de `is_multiturn_attack_verdict`
- [ ] Re-benchmark multi-turn scenarios

**Criterio de salida:** escenarios Crescendo en locked_v1 detectados como ALERT o CONTAIN; fp_suite verde.

### Fase 5 — EscalationJudge + migración CLI (1 PR)

- [ ] Juez solo post-ALERT; sesgo ALLOW en prompt
- [ ] `rage-bench --engine v2`
- [ ] Deprecar exports v1 en `pyproject.toml`

### Fase 6 — Limpieza (1 PR)

- [ ] Eliminar `access_policy.py`, `layer1_rules.py` monolito, dual-path en benchmark
- [ ] Actualizar `EVALUATION.md`, `QUICKSTART.md`, paper draft
- [ ] Tag `v2.0.0`

---

## 9. Portar / reescribir / descartar

### Portar (alto valor, bajo riesgo)

- `rage_core/layers/gateway.py` + tests
- `rage_core/models.py` (tipos base; extender en v2/models.py)
- `rage_core/metrics/auc_degradation.py`
- `rage_core/profiles/*.json` + `bot_profile.py`
- `rage_core/kb/*.json`
- `rage_core/llm/openai_compat.py`
- `rage_core/config/env_loader.py` (session keys)
- `eval_locked_v1/` + scripts freeze/baseline

### Reescribir

- `access_policy.py` → `l4_fusion.py`
- `layer1_rules.py` → `l0_hard.yaml` + `l3_hints`
- `chat_gate.py` → `user_gate.py`
- `session_judge.py` → `escalation.py`
- `benchmark/evaluator.py` → un solo `decide_v2()`
- `DefensePipeline` → `PipelineV2`

### Descartar o congelar

- Ratchet WARN→BLOCK en producto (opcional solo demo legacy `--v1`)
- L3 inline judge en hot path
- `eval_generalization` como métrica citada (mantener dev_eval)
- CLIs duplicados ya deprecados (`rage-chat`, `rage-chat-profile`)

---

## 10. Compatibilidad y rollout

| Superficie | v1 | v2 |
|------------|----|----|
| `rage-demo` | default | `--v2` opt-in → luego default |
| `rage-product-demo` | default | `--v2` primero |
| `rage-bench` | default | `--engine v2` |
| Tests CI default | v1 hasta fase 4 | switch en fase 5 |

Período de convivencia: **2 fases** (hasta fase 5) con A/B script `scripts/compare_v1_v2.sh`.

---

## 11. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Recall cae bajo 85% en locked_v1 | Solo subir recall vía L2 trajectory + L3 hints, nunca bajando umbrales L1/L4 sin fp_suite verde |
| fp_suite incompleto | Añadir turnos cada vez que un usuario reporte FP; PR obligatorio con caso |
| Complejidad dos pipelines | Feature flag `--v2`; eliminar v1 en fase 6 con deadline |
| Juez LLM reintroduce FP | Solo post-ALERT; default offline; métrica `judge_override_fp` en track B |

---

## 12. Criterios de éxito (definición de “hecho”)

1. **fp_suite:** 0 CONTAIN en 100% turnos benignos (CI bloqueante).
2. **eval_locked_v1:** 0 FP; recall ≥ 90% sin banda calibrada (número honesto en baseline JSON).
3. **Producto:** usuario benigno en restaurant/support puede completar flujo demo sin bloqueo.
4. **Ataques:** escenarios Crescendo/salami en locked_v1 ≥ ALERT; hard jailbreak → CONTAIN.
5. **Docs:** una sola tabla de veredictos; sin contradicción docstring/código.
6. **Secretos:** ninguna API key en disco tras PR session-api-keys.

---

## 13. Próximo paso inmediato

1. Aprobar este plan (o marcar cambios en umbrales/secciones).
2. Ejecutar **Fase 0** (merges pendientes).
3. Abrir PR **Fase 1** (`cursor/rage-v2-skeleton-6225`): esqueleto `rage_core/v2/` + `tests/fp_suite/`.

---

## Apéndice A — Comparación veredicto v1 vs v2

| Situación v1 | v2 propuesto |
|--------------|--------------|
| L3 suspicious → juez → block | WATCH o ALERT; chat continúa |
| policy_would_block multi-turn L2 0.36 | ALERT hasta turn ≥ 3 + trajectory |
| L1 match export benigno | L1 veto → ALERT máximo |
| L1 match “ignore instructions” | L0 → CONTAIN |
| Gateway bloquea INSERT | ToolGateway block (no es CONTAIN de chat) |

## Apéndice B — Comandos de verificación (post-implementación)

```bash
uv sync
uv run pytest tests/fp_suite/ -q
uv run pytest tests/v2/ -q
uv run pytest tests/ -q                    # v1 regression hasta fase 6
./scripts/run-bench-locked.sh --engine v2
uv run rage-product-demo --profile restaurant --offline --v2
```
