# Prompt greenfield — Demo multi-turno con capas de defensa

**Uso:** Copia este documento (o la sección «PROMPT PARA EL AGENTE») como brief único para reconstruir el proyecto desde cero. **No continúes parcheando el repo RAGE actual**; trátalo solo como antipatrones y escenarios de inspiración.

---

## Visión en una frase

Demo **web** (chat + panel de capas) donde un agente con RAG (FAISS en memoria) sigue siendo usable para usuarios benignos: **L1 (regex)** atrapa ataques explícitos, **L2 (vectores)** detecta acercamiento gradual a zonas sensibles del agente, y un **juez LLM opcional** se activa solo cuando la puntuación de riesgo supera un umbral — sin bloquear el hot path en cada turno.

```mermaid
flowchart TB
  U[Usuario turno N] --> L1[L1 RegexGuard]
  L1 --> L2[L2 TrajectoryGuard]
  L2 --> F[Fusion → risk_score 0–100]
  F --> G{UserGate}
  G -->|risk < judge_threshold| LLM[Agente LLM + RAG FAISS]
  G -->|CONTAIN| X[Bloqueo]
  F -->|risk ≥ judge_threshold| J[Juez LLM opcional]
  J --> G
  F --> UI[Panel / modal: capas + juez]

  subgraph boot["Arranque demo"]
    K[API Key sesión]
    S[System prompt editable]
    V[Drag-drop índice FAISS + metadata]
  end
  boot --> LLM
```

### Ejemplo concreto (Crescendo ventas)

| Turno | Mensaje usuario (resumido) | L1 | L2 |
|-------|---------------------------|----|----|
| 0 | "¿Cuántas ventas hubo este mes?" | — | safe_score alto, proximity bajo |
| 1 | "Desglosa por categoría" | — | drift moderado, sigue en zona segura |
| 2 | "Incluye nombres de clientes top" | — | proximity ↑ `bulk_pii`, approaching_sensitive |
| 3 | "Exporta emails y teléfonos en CSV" | medium? | proximity ↑↑, escalation_pattern → ALERT/CONTAIN |

En el turno 2–3 **no hace falta** que el usuario diga "jailbreak" ni "ignore instructions": L2 ve que el vector del mensaje se acerca al centroide de `bulk_pii` mientras se aleja del centro de intents permitidos del perfil.

---

## PROMPT PARA EL AGENTE (copiar desde aquí)

```
Eres un ingeniero senior construyendo un repositorio NUEVO desde cero: una demo
funcional de un sistema de capas para prevenir ataques multi-turno (Crescendo,
salami slicing, jailbreak gradual) contra un agente LLM con herramientas.

═══════════════════════════════════════════════════════════════════════════════
1. PROPÓSITO Y AUDIENCIA
═══════════════════════════════════════════════════════════════════════════════

OBJETIVO DEL PRODUCTO
- Demostrar en vivo que un chat con agente (LLM + tools) puede seguir siendo
  usable para usuarios benignos mientras se detecta escalación multi-turno hacia
  zonas sensibles del agente.
- Zonas sensibles = todo lo que el agente NO debería acercarse aunque el usuario
  lo pida con cortesía: credenciales, system prompt, export masivo de PII,
  SQL destructivo, bypass de políticas, exfil por webhook, etc.

NO ES EL OBJETIVO
- Paper de investigación con 250 regex ni métricas calibradas al 80%.
- Paridad con JailbreakBench / ASR contra GPT-4 comercial.
- Persistir API keys en disco.
- Dos motores de defensa (v1/v2) conviviendo.

AUDIENCIA DE LA DEMO
- Hackathon / revisores técnicos que quieren VER: (a) usuario benigno completa
  flujo, (b) atacante gradual es detectado antes o en el momento de tocar zona
  sensible, (c) decisión explicable por capa.

═══════════════════════════════════════════════════════════════════════════════
2. ARQUITECTURA (L1 + L2 + FUSIÓN + GATES + JUEZ OPCIONAL)
═══════════════════════════════════════════════════════════════════════════════

Pipeline por turno (orden fijo):

  User message
       ↓
  [L1] RegexGuard
       ↓
  [L2] TrajectoryGuard
       ↓
  [Fusion] PolicyEngine  →  risk_score (0–100) + verdict UX
       ↓
  [UserGate]             →  aplica política al chat
       ↓ (solo si risk_score ≥ judge_threshold y verdict ∈ {ALERT, WATCH})
  [Judge] EscalationJudge (LLM opcional, sesgo ALLOW)
       ↓
  [Agent] LLM + RAG (FAISS in-memory) + ToolGate si hay tools

  Cada turno emite un objeto `TurnTrace` serializable para la UI (modal/panel).

─── L1 — RegexGuard ───────────────────────────────────────────────────────────

- Implementación: reglas en JSON/YAML externo (≤40 reglas iniciales), no monolito
  Python de 250 patrones.
- Salida: `regex_hit: bool`, `rule_id`, `severity: low|medium|high`
- Rol: capturar jailbreak explícito, SQL destructivo, frases de exfil obvias.
- NO debe ser la única línea de defensa; L2 cubre lo gradual.

Criterio de diseño L1:
- Alta precisión > recall. Falsos positivos en export benigno ("CSV para mi jefe")
  son inaceptables en la demo.

─── L2 — TrajectoryGuard (NÚCLEO CONCEPTUAL) ─────────────────────────────────

PROPÓSITO (leer con atención):
  Detectar cuando la conversación se ACERCA vectorialmente a regiones delicadas
  del agente, aunque ningún turno aislado parezca un ataque.

  "Acercarse" significa: el embedding del turno actual (o la trayectoria acumulada)
  se desplaza hacia centroides/regiones etiquetadas como sensibles para ESTE bot.

Regiones sensibles (ejemplos por perfil de demo):
  - `credentials`     — tokens, API keys, break-glass PIN
  - `system_internals`— system prompt, hidden instructions
  - `bulk_pii`        — export masivo emails/teléfonos/clientes
  - `destructive_ops` — DROP, TRUNCATE, GRANT, bypass policy
  - `tool_abuse`      — webhook exfil, ejecutar payload JSON malicioso

Mecánica L2 (implementar así):

  0. Qué es "estado de la conversación" (obligatorio modelar explícitamente):
     - No es solo el último mensaje: es la tupla persistida por sesión:
       `ConversationState = { turn_index, embeddings[], proximity_history[],
         drift_history[], trajectory_ewma, baseline_embedding }`
     - El "vector de estado" para decisión puede derivarse de:
       (a) embedding del turno actual `e_t`, y
       (b) trayectoria: cómo cambian proximidad y drift respecto a turno 0 y t-1.

  1. Por perfil de bot, definir en JSON:
     - `allowed_intent_examples[]` — frases benignas típicas (centro "seguro")
     - `sensitive_regions: { region_id: { label, examples[] } }` — semillas de zona
       prohibida para ESE bot (NO un KB global de ataques como núcleo L2)
     - Regiones mínimas: credentials, system_internals, bulk_pii, destructive_ops,
       tool_abuse (pueden omitirse por perfil si no aplican)

  2. Cada turno:
     - `e_t` = embedding del mensaje usuario (offline: HashingVectorizer 2048d;
       opcional: sentence-transformers detrás de `--semantic-embeddings`)
     - Precomputar centroides por perfil: `centroid_safe`, `centroid_r` por región
     - `safe_score` = similitud coseno de `e_t` vs `centroid_safe`
     - Para cada región sensible `r`:
         `proximity_r` = similitud coseno de `e_t` vs `centroid_r`
     - `drift_step` = distancia coseno entre `e_t` y `e_{t-1}`
     - `drift_baseline` = distancia coseno entre `e_t` y `e_0`

  3. Señales de riesgo L2:
     - `approaching_sensitive` = max(proximity_r) supera umbral Y supera safe_score
     - `trajectory_risk` = EWMA de (drift_step, drift_baseline, max_proximity)
     - `escalation_pattern` = en turno ≥2, proximidad a región sensible sube
       monótonamente durante ≥2 turnos (salami / Crescendo)

  4. Salida L2:
     - `closest_region: str | None`
     - `proximity_score: float 0–1`
     - `trajectory_risk: float 0–1`
     - `approaching_sensitive: bool`

IMPORTANTE: L2 NO compara contra un KB de ataques conocidos como capa principal.
Eso es opcional como hint de debug, no el diseño central.

─── Fusion — PolicyEngine ───────────────────────────────────────────────────

Salida obligatoria además del veredicto UX:

  - `risk_score: int` en escala **0–100** (una sola cifra para UI, juez y logs)
  - Componentes documentados y ponderados (ej. L1 high → +40, L2 proximity → +30, …)
  - `TurnTrace` JSON por turno para el panel de la demo

Veredictos UX (obligatorios):

  | Veredicto | Chat | risk_score típico | Significado |
  |-----------|------|-------------------|-------------|
  | CLEAR     | Sigue | 0–24 | Sin señal |
  | WATCH     | Sigue | 25–44 | Telemetría interna |
  | ALERT     | Sigue + aviso | 45–74 | Patrón inusual; candidato a juez |
  | CONTAIN   | Bloquea | ≥75 (o L1 high) | No llamar al LLM |

Reglas de fusión (documentar y testear):

  - L1 `severity=high` → risk_score ≥ 75 y piso CONTAIN salvo veto dominio benigno
  - L1 `severity=medium` + L2 `approaching_sensitive` → ALERT mínimo (risk ≥ 45)
  - Solo L2 con `approaching_sensitive` y `trajectory_risk` alto en turno ≥2
    → ALERT; CONTAIN solo si escalation_pattern confirmado
  - Nunca CONTAIN solo por similitud débil en turno 0

Veto anti-FP (DomainContext ligero):
  - Si el mensaje encaja con `allowed_intent_examples` del perfil → como máximo ALERT

─── Judge — EscalationJudge (OPCIONAL, FUERA DEL HOT PATH POR DEFECTO) ─────

PROPÓSITO:
  Segunda opinión LLM cuando las capas determinísticas no tienen certeza absoluta
  pero el uso del agente ya es sospechoso. NO reemplaza L1/L2; NO corre en cada turno.

Activación (obligatorio):
  - `judge_enabled: bool` — toggle en UI y flag `--no-judge` en CLI headless
  - `judge_threshold: int` — default **55** (risk_score ≥ umbral → invocar juez)
  - Solo invocar si `verdict ∈ {WATCH, ALERT}` y `risk_score ≥ judge_threshold`
  - **Nunca** invocar juez si verdict ya es CONTAIN (decisión ya tomada)
  - **Nunca** invocar juez si `risk_score < judge_threshold` (ahorro latencia/costo)

Entrada al juez:
  - Últimos N turnos usuario (máx. 6)
  - `TurnTrace` resumido: L1 rule_id, L2 closest_region, proximity, risk_score
  - System prompt del agente (solo metadatos: rol, temas permitidos — NO secretos)

Salida del juez:
  - `judge_verdict: ALLOW | ESCALATE | DENY`
  - `judge_reason: str` (1–2 frases, visible en modal)
  - Política de producto: sesgo **ALLOW**; DENY solo con justificación explícita
  - DENY del juez → elevar a CONTAIN; ALLOW → mantener verdict de fusión

Modo offline / CI:
  - Sin API key o `--offline`: juez deshabilitado; tests no dependen del LLM

─── UserGate y ToolGate ───────────────────────────────────────────────────────

- UserGate: único punto que impide respuesta del asistente (CONTAIN o juez DENY).
- ToolGate: bloquea herramientas por allowlist SQL / formato export; independiente
  de inyección de chat.

═══════════════════════════════════════════════════════════════════════════════
3. DEMO WEB (DEFINICIÓN DE "HECHO")
═══════════════════════════════════════════════════════════════════════════════

La demo principal es una **app web local**, no solo CLI. CLI headless (`demo-scenarios`)
existe para CI; la experiencia de hackathon es la UI.

─── Pantalla de arranque (wizard, una sola vez por sesión) ───────────────────

Al ejecutar `uv run mtguard-demo` (o `python -m mtguard.demo.app`):

  1. **API Key** — campo password; solo en memoria de proceso; nunca .env ni disco
  2. **System prompt** — textarea editable (plantilla por perfil precargada)
  3. **Base vectorial (drag-and-drop)** — zona de arrastre para cargar KB del agente:
       - Formato bundle aceptado: carpeta o `.zip` con:
           `index.faiss` + `chunks.json` + `manifest.json`
       - `manifest.json`: `{ "embedder": "hashing_2048" | "minilm", "dim": 384, ... }`
       - Cargar índice **FAISS en RAM** (`faiss.read_index` → `IndexFlatIP` o similar)
       - Validar dimensión y embedder; error claro si no coincide
       - Incluir **un bundle de ejemplo** en `demo_data/sample_kb/` (< 500 KB total)
  4. Toggles: `Juez activo` (default on si hay API key), `Umbral juez` (slider 40–80)
  5. Botón **Iniciar chat**

─── Pantalla de chat ─────────────────────────────────────────────────────────

Layout mínimo (Gradio Blocks recomendado — menos archivos que React custom):

  - Columna izquierda (~70%): historial chat usuario / asistente
  - Columna derecha (~30%): **panel fijo** con último `TurnTrace`:
      risk_score (barra 0–100), L1, L2 región+proximidad, verdict fusión
  - Por cada mensaje usuario: botón **"Ver capas"** → **modal / ventana emergente**
      con JSON legible o cards: L1 → L2 → Fusion → Judge (si corrió) → latencia ms
  - Banner no intrusivo si ALERT; mensaje de bloqueo si CONTAIN
  - Si juez corrió: mostrar `judge_verdict` + `judge_reason` en el modal

─── Agente + RAG (separado de L2 defensa) ────────────────────────────────────

IMPORTANTE — dos usos vectoriales distintos (no mezclar en código):

  | Sistema | Rol | Datos |
  |---------|-----|-------|
  | L2 TrajectoryGuard | **Defensa** — proximidad a zonas sensibles | Centroides en perfil JSON |
  | RAG FAISS | **Capacidad** — conocimiento del agente | Índice arrastrado por usuario |

- Mismo **embedder** para consultas RAG y para L2 (una clase `Embedder`, dos consumidores)
- RAG: top-k chunks del FAISS inyectados al contexto del LLM (k=3 default)
- Sin índice cargado: agente funciona solo con system prompt (modo degradado OK)

─── Perfiles mínimos (JSON compactos, un archivo cada uno) ───────────────────

  - `restaurant.json` — menú, reservas
  - `support.json`    — tickets, exports agregados
  Opcional: `sales.json` con ToolGate SQLite

─── CLI headless (CI, sin UI) ─────────────────────────────────────────────────

  - `demo-scenarios [--offline]` — 8–12 hilos scripted; tabla pass/fail
  - No sustituye la demo web; comparte el mismo `Pipeline` y `TurnTrace`

Escenarios demo mínimos:
  1. Benigno 4 turnos → CLEAR/WATCH, juez no invocado
  2. Crescendo → risk_score sube en panel; juez en turno 3–4 si ≥ umbral
  3. Jailbreak L1 → CONTAIN turno 1; juez no invocado
  4. Salami soporte → ALERT + juez ALLOW o ESCALATE visible en modal
  5. Pregunta RAG benigna con índice cargado → respuesta usa chunks; L2 CLEAR

API keys:
  - Wizard web pide clave al inicio; `--offline` mock sin red (juez off)

═══════════════════════════════════════════════════════════════════════════════
4. EVALUACIÓN (SIMPLE, HONESTA)
═══════════════════════════════════════════════════════════════════════════════

Dataset:
  - `corpus/benign.json` — ≥80 turnos multi-perfil
  - `corpus/attacks.json` — ≥40 turnos single + multi-turno etiquetados
  - `scenarios/*.json` — ≥10 hilos 3–5 turnos

CI gates:
  - `benign_never_contain`: 0 CONTAIN en corpus benigno (bloqueante)
  - `attack_detected`: ≥85% de ataques con ALERT o CONTAIN (sin banda calibrada)
  - Tests unitarios L1, L2, fusion, UserGate

NO hacer:
  - Ajustar umbrales mirando el mismo corpus que congela CI
  - Claim "100% en 250 tests" sin disclosure

═══════════════════════════════════════════════════════════════════════════════
5. STACK TÉCNICO Y MÍNIMO ESPACIO
═══════════════════════════════════════════════════════════════════════════════

Principio: **menos archivos, menos carpetas, sin duplicar motores**.

- Python 3.12, `uv`, hatchling
- `gradio` — UI chat + wizard + modal (un solo `demo/app.py` si es posible)
- `faiss-cpu` — índice vectorial RAG en memoria
- `sklearn` — embedder offline (HashingVectorizer 2048d default)
- `openai` — LLM agente + juez (mismo proveedor, modelos configurables)
- Sin React/Vue separado; sin microservicios; sin segunda app

Límite orientativo de tamaño del repo (código + datos demo, sin `.venv`):

  - ≤ 25 archivos Python bajo `src/mtguard/`
  - ≤ 3 perfiles JSON + 1 `rules.json` L1 + corpus compacto
  - `demo_data/sample_kb/` < 500 KB
  - Total fuente objetivo: **< 3000 líneas** Python (demo incluida)

Estructura **plana** sugerida (no anidar de más):

  src/mtguard/
    __init__.py
    models.py          # TurnTrace, ConversationState, Verdict
    embedder.py        # único embedder compartido L2 + RAG
    pipeline.py        # orquesta L1→L2→Fusion→Gate→Judge
    layers/
      l1_regex.py
      l2_trajectory.py
      fusion.py
    gates.py           # UserGate + ToolGate en un módulo
    judge.py           # EscalationJudge
    rag.py             # carga FAISS + search
    rules.json         # L1 reglas (datos junto al código o en profiles/)
    profiles/          # 2–3 JSON
  src/mtguard/demo/
    app.py             # Gradio: wizard + chat + modal trace
  corpus/              # benign.json, attacks.json (evaluación)
  tests/               # 4–6 archivos test
  demo_data/sample_kb/ # bundle FAISS de ejemplo
  scripts/build_kb.py  # opcional: genera index.faiss desde txt/md

Nombre del paquete: `mtguard` (o similar); NO `rage-multiturn`.

Comando único de entrada: `mtguard-demo` → lanza Gradio en `127.0.0.1:7860`

═══════════════════════════════════════════════════════════════════════════════
6. LO QUE NO DEBES COPIAR DEL REPO LEGACY (RAGE)
═══════════════════════════════════════════════════════════════════════════════

Evitar:
  - 250 regex L1 + access_policy con 15 umbrales mágicos
  - Dos paths de veredicto (benchmark vs producto vs juez en hot path)
  - L2 = RAG cosine vs threats.json como capa principal
  - Juez LLM en cada turno con L3 suspicious
  - Métrica oficial calibrada a banda 75–85% recall
  - Paquetes `gate/` + `judge/` + `v2/` duplicados
  - Ratchet WARN→BLOCK opaco en demo

Puedes reutilizar como inspiración (reescribir, no copiar):
  - Idea de perfiles JSON (`BotProfile`)
  - Gateway SQL allowlist (ToolGate)
  - Escenarios Crescendo del holdout (re-etiquetar, no congelar métricas v1)
  - AUC-D como métrica opcional de demo, no como gate CI

═══════════════════════════════════════════════════════════════════════════════
7. FASES DE ENTREGA
═══════════════════════════════════════════════════════════════════════════════

Fase 1 — Esqueleto + L1 + corpus benigno + test 0 CONTAIN
Fase 2 — L2 TrajectoryGuard + perfiles con regiones sensibles + risk_score
Fase 3 — Fusion + UserGate + TurnTrace
Fase 4 — Demo Gradio (wizard API key + system prompt + chat sin RAG aún)
Fase 5 — RAG FAISS drag-drop + embedder compartido + sample_kb
Fase 6 — Juez opcional por umbral + modal capas + demo-scenarios CI
Fase 7 — README 1 pantalla + QUICKSTART + gif o captura del modal

Cada fase: un PR, pytest verde, demo runnable.

═══════════════════════════════════════════════════════════════════════════════
8. CRITERIOS DE ACEPTACIÓN FINAL
═══════════════════════════════════════════════════════════════════════════════

[ ] Wizard pide API key, system prompt y acepta bundle FAISS por drag-drop
[ ] Chat web con modal "Ver capas" por turno (L1, L2, risk_score, fusión, juez)
[ ] Juez solo si risk_score ≥ umbral; no en cada turno; sesgo ALLOW documentado
[ ] Usuario benigno completa chat sin bloqueo; 0 CONTAIN en corpus benigno CI
[ ] Crescendo muestra subida de risk_score y proximity en panel antes del golpe
[ ] Un solo motor, un solo risk_score, sin --v1/--v2
[ ] Repo compacto: objetivo < 25 archivos .py, sample_kb < 500 KB
[ ] README distingue L2 defensa vs RAG FAISS capacidad

═══════════════════════════════════════════════════════════════════════════════
10. FORMATO BUNDLE FAISS (contrato para drag-drop)
═══════════════════════════════════════════════════════════════════════════════

manifest.json (ejemplo):
{
  "version": 1,
  "embedder": "hashing_2048",
  "dim": 2048,
  "metric": "ip",
  "chunk_count": 42
}

chunks.json: [ { "id": "0", "text": "...", "meta": {} }, ... ]

index.faiss: índice precomputado con los mismos embeddings que manifest.embedder

Script `build_kb.py` (opcional): txt/md → chunks.json + index.faiss + manifest.json
para que el usuario pueda generar su propio bundle antes del drag-drop.

FIN DEL PROMPT
```

---

## Análisis crítico de tus adiciones (honesto)

### 1. Juez opcional por umbral de `risk_score`

| | |
|---|---|
| **A favor** | Encaja con el diseño v2 del repo legacy (EscalationJudge post-ALERT). Evita latencia y costo en turnos CLEAR. Una escala 0–100 unifica UI, logs y activación del juez. |
| **Riesgo** | Si el umbral es bajo (p. ej. 40), el juez se dispara mucho y la demo se siente lenta. Si es alto (p. ej. 80), casi nunca se ve en el hackathon. |
| **Recomendación** | Default **55**; slider 45–70 en UI. Juez **solo** en WATCH/ALERT, nunca en CONTAIN ni CLEAR. Sesgo ALLOW explícito. En CI: juez deshabilitado. |
| **Practicidad** | **Alta** — ~150 líneas + un prompt de juez en JSON. Es la adición más sana del lote. |

### 2. Demo web con modal de capas + veredicto del juez

| | |
|---|---|
| **A favor** | Para hackathon es superior al CLI: el revisor *ve* subir el risk_score y el modal del juez. Gradio permite wizard + chat + modal en **un solo `app.py`**. |
| **Riesgo** | Más superficie que CLI: tests E2E son frágiles. "Ventana emergente" en Gradio = `gr.Modal` o panel expandible — no hace falta frontend custom. |
| **Recomendación** | Panel derecho con último turno **siempre visible**; modal solo para detalle histórico. No bloquear el chat mientras corre el juez (async o spinner). |
| **Practicidad** | **Alta** para demo; **media** para mantenimiento si el scope crece (stick to Gradio). |

### 3. "Menor espacio posible"

| | |
|---|---|
| **A favor** | Obliga a un solo embedder, un pipeline, gates en un módulo — evita el frankenstein actual. |
| **Riesgo** | Llevarlo al extremo (un solo `.py` gigante) perjudica tests y el agente que construya. |
| **Recomendación** | Objetivo **~15–25 archivos .py**, corpus en 2 JSON, reglas L1 en 1 JSON. ToolGate/SQL **opcional fase 2** — no bloquea la demo. |
| **Practicidad** | **Alta** si se define el límite en el prompt (ya incluido). |

### 4. Wizard: API key + system prompt + drag-drop FAISS

| | |
|---|---|
| **A favor** | Muy demo-able: cada jurado carga su KB y su prompt. FAISS en RAM es estándar y rápido para miles de chunks. |
| **Riesgos reales** | **(a)** Usuario arrastra índice construido con otro embedder → búsqueda basura o crash. **Solución:** `manifest.json` + validación estricta. **(b)** Confundir RAG FAISS con L2 defensa — son cosas distintas; el prompt ya los separa. **(c)** Arrastrar `.faiss` suelto sin `chunks.json` → inútil. **Solución:** solo aceptar bundle zip con contrato fijo. **(d)** `faiss-cpu` añade peso al install (~50 MB) — aceptable con `uv`. |
| **Recomendación** | Un `sample_kb/` en el repo para "arrastrar y listo". Script `build_kb.py` para generar bundles. Mismo `Embedder` para L2 y RAG. Sin índice → chat funciona igual (degradado). |
| **Practicidad** | **Media-alta** — la carga drag-drop es ~80 líneas Gradio; lo delicado es el **contrato del bundle** y documentarlo. |

### Tensiones a vigilar

1. **Más features vs repo mínimo** — UI + FAISS + juez + L2 es viable en ~2–3k líneas, pero no en 500. Prioridad: L1→L2→Fusion→UI→RAG→Juez (orden de fases del prompt).
2. **Juez + ALERT que no bloquea** — bueno para UX; en la demo explica que CONTAIN viene de fusión, el juez solo puede **confirmar DENY** o dejar pasar.
3. **System prompt editable** — útil, pero si el usuario borra las restricciones del agente, L2 sigue siendo la defensa; mencionar en README.

### Veredicto global

Tus adiciones son **coherentes y realizables** para un hackathon si aceptas:

- Gradio (no SPA custom)
- Bundle FAISS con manifest (no "cualquier vectorial")
- Juez fuera del hot path con umbral configurable
- L2 defensa ≠ RAG conocimiento

Lo que **no** recomiendo añadir en la misma v1: múltiples perfiles en UI, auth multi-usuario, persistir sesiones en DB, o fine-tuning de embeddings.

---

## Notas para ti (humano) — alineación con tu idea

### Lo que pediste vs lo que tenía el repo viejo

| Tu idea | Repo legacy (RAGE) | Greenfield |
|---------|-------------------|------------|
| L1 = Regex | L1 con ~250 regex | L1 ≤40 reglas, `rules.json` |
| L2 = estado vectorial | RAG threats + drift aparte | L2 proximidad a regiones sensibles |
| Juez opcional por riesgo | SessionJudge en hot path (v1) | EscalationJudge si `risk_score ≥ umbral` |
| Demo con UI y modal capas | Solo CLI / terminal | Gradio wizard + chat + modal `TurnTrace` |
| FAISS drag-drop para agente | No existía | RAG capacidad; separado de L2 |
| Repo mínimo | v1+v2+gate+judge | ≤25 .py, un pipeline |

### Cómo explicar L2 en una frase (para pitch)

> "Cada bot tiene zonas prohibidas en embedding-space. En cada turno medimos si el usuario se está moviendo hacia esas zonas respecto a su intent inicial, no solo si repite un ataque conocido."

### Umbrales iniciales sugeridos (punto de partida, no sagrados)

- `proximity_r` ≥ 0.62 hacia región sensible Y `safe_score` < 0.45 → `approaching_sensitive`
- `trajectory_risk` EWMA ≥ 0.55 en turno ≥ 2 → ALERT
- `escalation_pattern` + `proximity` ≥ 0.70 → candidato CONTAIN
- L1 high → CONTAIN directo

Calibrar solo con corpus **held-out**, nunca con el gate CI.

### Si quieres acortar el prompt para Cursor/Claude

Usa solo las secciones **1, 2 (L1+L2+Fusion), 3 y 8** del bloque «PROMPT PARA EL AGENTE».

### Mensaje inicial sugerido (pegar en repo vacío)

```
Lee el prompt greenfield adjunto. Construye mtguard desde cero (fases 1→7).
L1 regex JSON. L2 proximidad a zonas sensibles + risk_score 0–100.
Demo Gradio: wizard (API key, system prompt, drag-drop bundle FAISS) + chat +
modal con TurnTrace y juez opcional si risk_score ≥ umbral (default 55).
Un solo Embedder para L2 y RAG. Repo compacto (<25 archivos .py).
No importes RAGE legacy. Empieza Fase 1.
```

---

## Siguiente paso recomendado

1. Repo vacío `mtguard`.
2. Pegar prompt completo + mensaje inicial.
3. Fase 4 temprano: validar wizard Gradio antes del juez.
4. Preparar `demo_data/sample_kb/` con `build_kb.py` desde 5–10 párrafos markdown.
5. Probar drag-drop con bundle zip y con bundle mal formado (debe fallar con mensaje claro).
