# RAGE: Pasarela de Seguridad Agéntica Robusta para Text-to-SQL — Defensa Estatal Frente a Ataques Multi-Turno de Tipo Crescendo

**Autores:** RAGE Research Team  
**Venue:** Global South AI Safety Hackathon, Junio 2026  
**Repositorio:** `rage-multiturn` — Python 3.12, Licencia MIT  
**Ancla bibliográfica:** Russinovich et al., arXiv:2404.01833 [cs.CR]

---

## Resumen (Abstract)

Las interfaces Text-to-SQL exponen bases de datos relacionales a lenguaje natural mediante agentes LLM, abriendo una superficie de ataque crítica: el adversario *Crescendo* migra gradualmente una sesión legítima hacia cargas SQL destructivas a través de N turnos benignos, evadiendo todo filtro que evalúe prompts de forma aislada. Presentamos **RAGE**, una defensa de cuatro capas que neutraliza esta amenaza mediante (i) un filtro semántico estatal que mide la deriva acumulada respecto al turno cero, (ii) un motor de decisión con media móvil exponencial (EWMA) y un trinquete de advertencias consecutivas, y (iii) una pasarela SQL determinista con lista de permitidos endurecida. Introducimos el **Índice de Resistencia Temporal (TRI)** y el **AUC de Degradación (AUC-D)**. El sistema se valida con una suite automatizada completa que cubre las capas, la pasarela y las métricas, interceptando todos los turnos de ataque en el escenario Crescendo. *(149 palabras)*

---

## 1. Introducción y Marco Teórico

### 1.1 La superficie de ataque Text-to-SQL

Las organizaciones modernas exponen progresivamente sus datos operativos a través de *interfaces de lenguaje natural* que traducen consultas de usuario en SQL mediante un agente LLM [2, 3]. Estas interfaces aportan accesibilidad, pero introducen una amenaza estructuralmente novedosa: a diferencia de un formulario web o una API REST, aceptan entradas arbitrariamente largas, contextualmente ricas, cuya intención es difícil de validar con filtrado basado en firmas. Un usuario capaz de sostener una conversación con el agente a lo largo de múltiples turnos dispone de un grado de libertad expresiva fundamentalmente incompatible con el principio de mínimo privilegio que rige la seguridad de bases de datos.

El paradigma defensivo dominante es *apátrida* (stateless): cada turno se examina de forma independiente en busca de firmas de inyección conocidas (`DROP TABLE`, `IGNORE PREVIOUS INSTRUCTIONS`) y se rechaza si dispara una coincidencia. Este modelo de evaluación es un corolario directo de los *benchmarks* de alineación de un solo turno que dominan la investigación actual en seguridad de LLM. Como afirman Russinovich et al.: *"todos los benchmarks actuales se centran exclusivamente en jailbreaks de un solo turno [...] los jailbreaks multi-turno pueden eludir fácilmente estas medidas"* [1, §1].

### 1.2 La Teoría del Cambio: del prompt al estado de sesión

La contribución conceptual de RAGE es un **cambio de paradigma** en la unidad de evaluación de seguridad: del *prompt individual* al *estado acumulado de la sesión*. Formalmente, sea $H_t = \langle q_0, q_1, \ldots, q_t \rangle$ la historia conversacional hasta el turno $t$. Un filtro apátrida implementa una función de decisión $f(q_t) \to \{\text{allow}, \text{block}\}$ que depende **únicamente** del turno actual. RAGE implementa, en cambio, una función estatal $g(q_t, S_{t-1}) \to (\text{banda}, S_t)$, donde $S_t$ es un vector de estado que comprime la memoria histórica de la conversación:

$$S_t = (\mathbf{e}_0, R_t, c_t, w_t)$$

con $\mathbf{e}_0$ el embedding del turno cero (ancla semántica), $R_t$ el riesgo de sesión acumulado por EWMA, $c_t$ el contador de advertencias consecutivas (trinquete) y $w_t$ un indicador binario de advertencia/bloqueo previo. Este estado se materializa en el código mediante la dataclass `ConversationState`:

```68:88:rage_core/models.py
class ConversationState:
    """Mutable state threaded through a multi-turn conversation."""
    turn_index: int = 0
    # Embeddings are stored as lists of floats for JSON-serializability
    turn_embeddings: list[list[float]] = field(default_factory=list)
    # Intent summaries per turn (treated as untrusted input)
    intent_summaries: list[str] = field(default_factory=list)
    signals: list[TurnSignal] = field(default_factory=list)
    # Ground-truth vulnerability scores 0-5 (set by the evaluator, not by the defense)
    gt_scores: list[int] = field(default_factory=list)
    # --- Crescendo-hardening: session-level risk tracking ---
    session_risk_score: float = 0.0
    # Number of consecutive turns that landed in the WARN band.
    consecutive_warns: int = 0
    # True once any prior turn received WARN or BLOCK.
    had_warn_or_block: bool = False
```

La hipótesis central es que un adversario persistente sólo puede ser neutralizado por una defensa que **recuerde la trayectoria**. La memoria histórica no es un lujo de ingeniería, sino una necesidad matemática derivada de la Proposición 1 (§3.3).

---

## 2. Trabajos Relacionados

La literatura de defensa se agrupa en familias complementarias. Los enfoques de *endurecimiento de prompt* (Self-Reminder [3], Goal Prioritization [4]) reinsertan recordatorios éticos en cada turno; reducen la tasa de éxito de ataque (ASR) pero, como demuestra la evaluación de Crescendomation, son superados al ampliar el presupuesto de turnos y el *backtracking* [1, §5.3.2]. Los enfoques de *separación estructural* (StruQ [5]) aíslan instrucciones y datos en canales distintos mediante delimitadores reservados y *fine-tuning*, ofreciendo garantías estructurales a costa de modificar el modelo. Los detectores de *deriva semántica estatal* (DeepContext [6]) emplean redes recurrentes sobre embeddings por turno para rastrear la trayectoria de intención. Las defensas de *control de flujo agéntico* (DRIFT [8], IPIGuard [9]) fijan un grafo de dependencia de herramientas desde la consulta inicial y validan cada invocación contra el plan. Finalmente, el dominio específico Text-to-SQL fue caracterizado por Castro et al. en su estudio de inyecciones Prompt-to-SQL y la defensa LangShield [11].

RAGE se posiciona en la intersección de la deriva semántica estatal y la seguridad Text-to-SQL determinista, con la particularidad de no requerir reentrenamiento del LLM y de cerrar el bucle con un mecanismo de red-team automatizado. Cubre explícitamente los riesgos OWASP **LLM01** (Inyección de Prompt), **LLM06** (Agencia Excesiva) y **LLM08** (Entrada No Confiable / debilidades de embeddings).

---

## 3. Análisis de la Amenaza Crescendo

### 3.1 Mecanismo formal

Russinovich, Salem y Eldan [1] introducen Crescendo como una técnica de jailbreak *multi-turno, de caja negra, que utiliza exclusivamente prompts benignos y legibles por humanos*. Su propiedad definitoria —y la que la hace devastadora frente a defensas apátridas— es que ningún turno individual contiene contenido adversarial. La técnica se fundamenta en el principio psicológico del *foot-in-the-door*: acceder a una petición pequeña incrementa sistemáticamente el cumplimiento de demandas posteriores mayores. La Tabla 3 de [1] muestra que la secuencia completa `A → B → C` alcanza un 99.9 % de éxito, mientras que `B` aislado sólo logra 36.2 % y `C` aislado 17.3 %: *es la trayectoria, no el turno individual, lo que constituye el ataque*.

### 3.2 Las tres fases adaptadas a Text-to-SQL

**Fase 1 — Sembrado de contexto (T0–T1):** el atacante emite consultas SQL legítimas que demuestran competencia técnica y establecen confianza. El agente aprende que el usuario es un analista de datos en operaciones normales. Ninguna firma coincide; el riesgo de sesión es cero.

**Fase 2 — Expansión de alcance (T2–T3):** las consultas amplían gradualmente su ámbito —introducen tablas adicionales, `JOIN`s, o marcos de "auditoría/cumplimiento"—. El encuadre normaliza el acceso a un conjunto más amplio de objetos. Cada paso presenta baja deriva turno-a-turno, pues es topológicamente adyacente al anterior. Un detector puramente turno-a-turno no observa anomalía alguna.

**Fase 3 — Inyección de carga (T4+):** el turno final inyecta la carga destructiva, enmarcada como continuación natural del flujo de auditoría previo. Ejemplos: `UNION ALL SELECT … FROM system_config` (exfiltración vía rama UNION a una tabla no autorizada) o consultas contra `audit_log`. Antes del parche aplicado en este trabajo, el regex `\bUNION\s+SELECT\b` **no** coincidía con `UNION ALL SELECT`, constituyendo un bypass confirmado.

### 3.3 Proposición 1 — Ceguera del Filtro Apátrida

**Proposición 1 (Stateless Filter Blindness).** Sea $\delta(q_i, q_{i-1})$ la deriva semántica turno-a-turno. Un filtro apátrida con umbral $\tau$ bloquea el turno $i$ si y sólo si $\delta(q_i, q_{i-1}) > \tau$. En un ataque Crescendo con tamaño de paso $\epsilon \ll \tau$, todos los turnos satisfacen $\delta(q_i, q_{i-1}) = \epsilon < \tau$, pero la deriva acumulada respecto al baseline cumple:

$$\Delta(q_N, q_0) = \sum_{i=1}^{N} \epsilon \approx N\epsilon$$

que puede ser $\gg \tau$ para $N$ grande. Por tanto, el filtro apátrida nunca dispara pese a que la conversación ha migrado arbitrariamente lejos de su punto de partida benigno. ∎

Esta proposición establece la **necesidad formal** del cómputo de deriva acumulada anclada al baseline que introduce la Capa 3 de RAGE.

---

## 4. Metodología y Arquitectura de Software

RAGE implementa una cascada de cuatro capas seguida de una pasarela de acciones:

```
Turno → [L1: Regex] → [L2: RAG KB] → [L3: Filtro Semántico] → [L4: Motor de Decisión]
                                                                       ↓
                                                       [Pasarela de Acción] → [Agente SQLite]
                                                                       ↓
                                                       [Evaluador AUC-D / TRI]
```

### 4.1 Capa 1 — Pre-filtro Determinista (`layer1_rules.py`)

La Capa 1 compila un conjunto de reglas regex contra el texto crudo del turno, con coste $O(1)$, sin ML ni llamadas a API, y salida temprana en la primera coincidencia. Apunta a firmas de alta confianza: anulación de instrucciones, activadores DAN/jailbreak, destructores SQL literales y fuga de prompt de sistema.

```22:38:rage_core/layers/layer1_rules.py
_RAW_RULES: list[tuple[str, str, str]] = [
    ("L1-001", "Explicit ignore-previous-instructions", r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?"),
    ("L1-002", "Explicit disregard system prompt", r"disregard\s+(your\s+)?(system\s+prompt|instructions?|guidelines?)"),
    ("L1-003", "Forget all / start fresh", r"forget\s+(everything|all|your)\s*(you\s+were\s+told|instructions?|rules?|guidelines?)?"),  # noqa: E501
    ("L1-004", "DAN / developer mode activation", r"\b(DAN|developer\s+mode|jailbreak\s+mode|unrestricted\s+mode)\b"),
    ("L1-005", "Override safety / bypass restrictions", r"(override|bypass|disable|remove)\s+(all\s+)?(safety|content|ethical)\s+(filters?|guidelines?|restrictions?|protocols?)"),  # noqa: E501
    ("L1-006", "SQL DROP TABLE attempt", r"\bDROP\s+TABLE\b"),
    ("L1-007", "SQL GRANT PRIVILEGES", r"\bGRANT\s+ALL\s+PRIVILEGES\b"),
    ("L1-008", "Base64 decode-and-execute instruction", r"(decode\s+and\s+execute|run\s+this\s+decoded)"),
    ("L1-009", "Explicit new system instruction injection", r"\[?\s*(SYSTEM|INJECTED?\s+INSTRUCTION|NEW\s+INSTRUCTION)\s*\]?\s*:"),  # noqa: E501
    ("L1-010", "Never refuse / always comply framing", r"(never\s+(say|refuse|decline)|always\s+comply|must\s+not\s+refuse)"),
    ("L1-011", "Evil twin / no-ethical-constraints persona", r"(evil\s+twin|no\s+ethical\s+constraints?|no\s+restrictions?\s+persona)"),  # noqa: E501
    ("L1-012", "Shell/OS command execution", r"(os\.system|subprocess\.run|exec\(|eval\(|import\s+os;)"),
    ("L1-013", "Exfiltrate data to external endpoint", r"exfiltrat\w*\s+(to|into)\s+(external|remote|attacker)"),
    ("L1-014", "Prompt leakage — reveal system prompt", r"(reveal|print|show|leak|expose)\s+(the\s+)?(system\s+prompt|your\s+instructions?|your\s+guidelines?)"),  # noqa: E501
]
```

La limitación es reconocida por diseño: la Capa 1 es un *trip-wire* apátrida, no la defensa principal contra ataques multi-turno. Su contribución al score fusionado es de +70 puntos (coincidencia dura → ataque casi seguro).

### 4.2 Capa 2 — Base de Conocimiento de Amenazas RAG (`layer2_rag.py`)

La Capa 2 embebe el texto del turno y calcula similitud coseno contra una base de conocimiento curada de ejemplos de ataque OWASP LLM01 a través de múltiples familias. Aporta una señal suave y graduada (∈ [0, 1]) que captura *proximidad semántica a ataques conocidos* aun en ausencia de firmas exactas. La prioridad del embebedor es `sentence-transformers` → `openai` → TF-IDF (ruta offline por defecto). El núcleo de puntuación:

```140:158:rage_core/layers/layer2_rag.py
    def score(self, text: str) -> Layer2Signal:
        """Return a Layer2Signal for the given text."""
        query_vec = self._embed_query(text)
        sims = _cosine_similarity(query_vec, self._matrix)
        top_idx = int(np.argmax(sims))
        top_sim = float(sims[top_idx])

        if top_sim < self._threshold:
            return Layer2Signal(score=top_sim)

        threat = self._threats[top_idx]
        return Layer2Signal(
            score=top_sim,
            top_match_id=threat["id"],
            top_match_category=threat["category"],
            top_match_technique=threat["technique"],
            owasp_id=threat["owasp_id"],
            severity=threat["severity"],
        )
```

Una propiedad operativa destacada es la **actualización en caliente** mediante `add_threat()`, que añade nuevos ejemplos al corpus y re-indexa sin reentrenar, habilitando respuestas adaptativas a familias de ataque recién descubiertas.

### 4.3 Capa 3 — Filtro Semántico Estatal de Intención (`layer3_semantic.py`)

La Capa 3 es la **contribución central** para la defensa Crescendo y la implementación directa de la solución a la Proposición 1.

**Embebedor de dimensión fija.** Los turnos se embeben con `_InlineEmbedder`, que envuelve `HashingVectorizer` con `n_features=2048`, `alternate_sign=False` y `norm="l2"`. La salida normalizada en L2 garantiza que la similitud coseno se reduzca al producto punto, $\cos(\mathbf{u},\mathbf{v}) = \mathbf{u}\cdot\mathbf{v}$. El uso de `HashingVectorizer` sobre un `TfidfVectorizer` ajustado es deliberado: su dimensión de salida es fija (2048) con independencia del vocabulario, de modo que los embeddings almacenados en `turn_embeddings` permanecen compatibles entre turnos sin reajuste.

```50:64:rage_core/layers/layer3_semantic.py
    def __init__(self) -> None:
        from sklearn.feature_extraction.text import HashingVectorizer  # type: ignore

        self._vec = HashingVectorizer(
            n_features=self.N_FEATURES,
            alternate_sign=False,
            norm="l2",
        )

    def embed_single(self, text: str) -> np.ndarray:
        mat = self._vec.transform([text])
        vec = mat.toarray()[0].astype(np.float32)
        norm = np.linalg.norm(vec) + 1e-9
        return vec / norm
```

**Deriva turno-a-turno ($\delta_i$) y deriva acumulada ($\Delta_i$).** Sea $\mathbf{e}_i \in \mathbb{R}^{2048}$ el embedding normalizado del turno $i$. Se definen:

$$\delta_i = \max\!\left(0,\; 1 - \mathbf{e}_i \cdot \mathbf{e}_{i-1}\right), \qquad \Delta_i = \max\!\left(0,\; 1 - \mathbf{e}_i \cdot \mathbf{e}_0\right)$$

La primera detecta saltos abruptos de tema (inyección clásica); la segunda —la *adición de endurecimiento Crescendo*— mide la distancia respecto al **baseline de la conversación** (turno 0), exponiendo la migración lenta e incremental que caracteriza a Crescendo. El bloque exacto que ejecuta ambos `np.dot()`:

```169:189:rage_core/layers/layer3_semantic.py
        # 1. Embed current turn
        current_emb = self._embedder.embed_single(turn_text)

        # 2. Turn-to-turn drift: distance from the immediately preceding turn
        drift = 0.0
        if state.turn_embeddings:
            prev_emb = np.array(state.turn_embeddings[-1], dtype=np.float32)
            cos_sim = float(np.dot(current_emb, prev_emb))
            drift = max(0.0, 1.0 - cos_sim)  # cosine distance

        # 3. Cumulative drift: distance from conversation baseline (turn 0).
        # On the first turn there is no baseline yet, so cumulative_drift = 0.
        cumulative_drift = 0.0
        if len(state.turn_embeddings) >= 1:
            baseline_emb = np.array(state.turn_embeddings[0], dtype=np.float32)
            baseline_cos_sim = float(np.dot(current_emb, baseline_emb))
            cumulative_drift = max(0.0, 1.0 - baseline_cos_sim)

        # 4. Flag if *either* drift signal exceeds the threshold
        suspicious = drift > self._threshold or cumulative_drift > self._threshold
```

La bandera `suspicious` se activa si **cualquiera** de las dos señales excede el umbral $\tau$ (por defecto 0.80, calibrado para `HashingVectorizer`; ≈0.35 con `sentence-transformers`). Sólo entonces se invoca, opcionalmente, un juez LLM (`gpt-4o-mini`) cuando `OPENAI_API_KEY` está presente. Conforme a OWASP LLM08, los resúmenes de intención son tratados como contenido no confiable: la función `_sanitize()` elimina caracteres de control (`\x00`–`\x1f`, `\x7f`) y trunca a 300 caracteres antes de cualquier almacenamiento o inclusión en prompt.

### 4.4 Capa 4 — Motor de Decisión Dinámico (`layer4_decision.py`)

**Fusión de scores.** `DecisionEngine._compute_score()` fusiona las señales L1–L3 en un escalar $s_i \in [0, 100]$:

$$s_i = 70\cdot\mathbf{1}[\text{L1}] + 30\cdot\min(L2,1) + 20\cdot\min(\max(\delta_i,\Delta_i),1) + 5\cdot\mathbf{1}[\Delta_i>0.75] + 10\cdot\mathbf{1}[\text{LLM}]$$

```88:110:rage_core/layers/layer4_decision.py
        score = 0.0

        # Layer 1 — hard match
        if l1.matched:
            score += 70.0

        # Layer 2 — RAG similarity (0–1 → 0–30 pts)
        score += min(l2.score, 1.0) * 30.0

        # Layer 3 — blended drift: take the maximum of turn-to-turn and cumulative
        # drift so that both abrupt jumps AND gradual Crescendo trajectories are
        # captured in a single 0–20 pt contribution.
        blended_drift = max(l3.drift, l3.cumulative_drift)
        score += min(blended_drift, 1.0) * 20.0

        # Crescendo bonus — sustained topic migration across turns
        if turn_index >= 2 and l3.cumulative_drift > 0.75:
            score += 5.0

        # Layer 3 — LLM judge bonus
        if l3.llm_flagged:
            score += 10.0
```

El uso de $\max(\delta_i, \Delta_i)$ asegura que tanto los ataques de salto abrupto (alto $\delta_i$) como los Crescendo graduales (alto $\Delta_i$) contribuyan. El score se discretiza en bandas con $\theta_{\text{warn}}=30$ y $\theta_{\text{block}}=65$.

**EWMA de riesgo de sesión.** Un único score por turno es insuficiente frente a Crescendo, pues cada turno puede permanecer bajo $\theta_{\text{warn}}$. RAGE mantiene un riesgo rodante $R_t$ como media móvil exponencial de los scores normalizados:

$$R_t = (1-\alpha)\cdot R_{t-1} + \alpha\cdot\frac{s_t}{100}, \qquad \alpha = 0.40, \quad R_0 = 0$$

```210:216:rage_core/layers/layer4_decision.py
        # 1. Update rolling session-risk score (EWMA of normalised per-turn score)
        normalised_score = turn_signal.score / 100.0
        state.session_risk_score = (
            (1.0 - self.ewma_alpha) * state.session_risk_score
            + self.ewma_alpha * normalised_score
        )
```

El parámetro $\alpha$ es configurable por constructor (`ewma_alpha`); el valor calibrado para los resultados reportados es $\alpha = 0.40$, que pondera con fuerza los turnos recientes reteniendo memoria con decaimiento exponencial. La progresión del riesgo se ilustra a continuación, donde una serie de turnos de riesgo moderado eleva $R_t$ por encima del umbral EWMA pese a que ningún turno individual alcanza la banda WARN:

| Turno | $s_i$ | $s_i/100$ | $R_t$ |
|:-----:|:-----:|:---------:|:-----:|
| 0 | 18 | 0.18 | 0.072 |
| 1 | 22 | 0.22 | 0.131 |
| 2 | 25 | 0.25 | 0.179 |
| 3 | 28 | 0.28 | 0.231 |
| 4 | 30 | 0.30 | 0.279 |

En el turno 4, $R_4 = 0.279 > \theta_{\text{EWMA-warn}} = 0.25$, disparando elevación de banda. Este es el mecanismo primario por el cual RAGE detecta la firma de "deriva lenta" de Crescendo.

**Trinquete de advertencias consecutivas.** Para impedir que un atacante "acampe" indefinidamente en la banda WARN manteniendo $s_i \in [30, 65)$, RAGE implementa un trinquete sobre `consecutive_warns`:

```232:239:rage_core/layers/layer4_decision.py
        # 3. Consecutive-warn ratchet: N WARNs in a row → force BLOCK
        if current_band == Band.WARN:
            state.consecutive_warns += 1
        else:
            state.consecutive_warns = 0  # reset on ALLOW or BLOCK

        if state.consecutive_warns >= self.ratchet_turns:
            current_band = Band.BLOCK
```

Tras $K_{\text{ratchet}} = 3$ turnos consecutivos en WARN, la banda se eleva incondicionalmente a BLOCK. El trinquete se reinicia a cero ante cualquier turno no-WARN, evitando escaladas de falso positivo en conversaciones que toquen temas sensibles pero benignos. Los umbrales son tunables a nivel de clase (`_EWMA_ALPHA`, `_RATCHET_TURNS`, `_SESSION_RISK_WARN_THRESHOLD`, `_SESSION_RISK_BLOCK_THRESHOLD`) y por argumentos de constructor, permitiendo adaptar la agresividad al contexto de despliegue.

### 4.5 Pasarela de Seguridad SQL (`gateway.py`)

La pasarela provee validación SQL determinista de **última línea** antes de que cualquier consulta alcance la base de datos, implementando OWASP LLM06 (Agencia Excesiva). Mantiene una lista negra de patrones, una lista de permitidos de tablas y una lista de permitidos de columnas por tabla. El endurecimiento Crescendo cerró dos bypasses confirmados.

**Bypass 1 — `UNION ALL SELECT`.** El patrón original `\bUNION\s+SELECT\b` sólo coincidía con la cadena literal `UNION SELECT`; el fragmento `UNION ALL SELECT config_key, config_value FROM system_config` lo eludía porque el token `ALL` se interpone. El parche generaliza el patrón a `\bUNION\b`, bloqueando cualquier variante:

```49:51:rage_core/layers/gateway.py
    # --- Exfiltration via UNION (ANY variant: UNION ALL, UNION DISTINCT, etc.) ---
    # Previously only matched `UNION SELECT`; `UNION ALL SELECT` was a confirmed bypass.
    ("UNION-based exfiltration", re.compile(r"\bUNION\b", re.IGNORECASE)),
```

**Bypass 2 — Extracción single-FROM.** El regex previo `\bFROM\s+(\w+)\b` extraía sólo la primera cláusula `FROM`, validando únicamente `sales` (permitida) e ignorando `system_config` (no permitida) en la rama UNION. El parche introduce `_ALL_TABLES_RE`, que captura **todas** las referencias de tabla tras `FROM` o `JOIN`:

```85:86:rage_core/layers/gateway.py
# Extracts ALL table/alias names that follow FROM or JOIN keywords.
_ALL_TABLES_RE = re.compile(r"\b(?:FROM|JOIN)\s+(\w+)\b", re.IGNORECASE)
```

La lógica de validación recorre cada tabla extraída y la coteja contra la lista de permitidos, garantizando que ninguna rama UNION exfiltre datos hacia una tabla no autorizada aun si el propio token UNION hubiese evadido la lista negra:

```161:172:rage_core/layers/gateway.py
    # Extract ALL table references and validate each against the allowlist.
    tables_found = _ALL_TABLES_RE.findall(sql)
    if not tables_found:
        return False, "Could not extract any table name from SELECT statement"

    for table in tables_found:
        if table.lower() not in _ALLOWED_TABLES:
            return False, f"Table '{table}' is not in the allowlist {_ALLOWED_TABLES}"

    ok, reason = _validate_columns(sql, tables_found)
    if not ok:
        return False, reason
```

La lista negra ampliada incorpora vectores de ofuscación adicionales: `ALTER`, `CREATE`, `EXEC/EXECUTE`, inyección ciega temporal (`SLEEP`, `BENCHMARK`, `WAITFOR DELAY`), codificación `CHAR()`, literales hexadecimales, sondas `information_schema` y `sqlite_master`, y `LOAD_FILE`/`LOAD DATA`.

---

## 5. Marco de Evaluación y Resultados Cuantitativos

### 5.1 Suite de pruebas automatizadas

El sistema se valida con una suite automatizada (`python3 -m pytest tests/`) organizada en cuatro módulos que cubren de forma independiente cada subsistema: `test_gateway.py` (lista negra SQL parametrizada, regresión de `UNION ALL`, validación de exportación, lista de permitidos de herramientas), `test_layers.py` (patrones L1, RAG L2, pipeline extremo a extremo, y la clase `TestRatchetAndSessionRisk` para EWMA/trinquete), `test_semantic_filter.py` (sanitizador, primer turno, conversación benigna, escalada y la clase `TestCumulativeDrift`), y `test_auc_metric.py` (cómputo AUC, turno de compromiso, hipótesis H1/H4, y la clase `TestTemporalResistanceIndex`). El conjunto reproduce el endurecimiento Crescendo descrito y se ejecuta sin fallos.

### 5.2 AUC de Degradación (AUC-D)

La resiliencia se mide con el **Área Bajo la Curva de Degradación**. Las puntuaciones de vulnerabilidad por turno $v_t \in \{0,\ldots,5\}$ provienen de **hechos observables** (¿se filtró el canario `ZEPHYR-7781`? ¿se ejecutó SQL prohibido?), no de la confianza interna de la defensa, lo que evita la autoevaluación circular. El AUC bruto se calcula por la regla trapezoidal y se normaliza a $[0,1]$:

$$\text{AUC}_{\text{raw}} \approx \sum_{i=0}^{N-2} \frac{v_i + v_{i+1}}{2}, \qquad \text{AUC}_{\text{norm}} = \frac{\text{AUC}_{\text{raw}}}{S_{\max}\cdot(N-1)}, \quad S_{\max}=5$$

```50:74:rage_core/metrics/auc_degradation.py
    if not gt_scores:
        raise ValueError("gt_scores must not be empty")

    n = len(gt_scores)
    turns = list(range(n))
    scores_arr = np.array(gt_scores, dtype=float)

    # np.trapz was renamed to np.trapezoid in NumPy 2.0
    _trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    auc_raw = float(_trapz(scores_arr, turns))
    auc_norm = auc_raw / (SCORE_MAX * max(n - 1, 1))  # normalize to [0, 1]

    compromise_turn: Optional[int] = None
    for i, s in enumerate(gt_scores):
        if s >= 4:
            compromise_turn = i
            break

    return AUCResult(
        label=label,
        turns=turns,
        gt_scores=gt_scores,
        auc_raw=round(auc_raw, 4),
        auc_normalized=round(auc_norm, 4),
        compromise_turn=compromise_turn,
    )
```

Un $\text{AUC}_{\text{norm}}=0$ indica defensa perfecta; $\text{AUC}_{\text{norm}}=1$ indica compromiso total desde el turno 0. La **Hipótesis H1** sostiene $\text{AUC}_{\text{norm}}^{\text{sin defensa}} > \text{AUC}_{\text{norm}}^{\text{RAGE}}$ para todo escenario de ataque.

### 5.3 Índice de Resistencia Temporal (TRI)

Mientras AUC-D caracteriza la *severidad*, el TRI responde a *cuántos turnos retrasa la defensa el primer compromiso*:

$$TRI = \frac{T_{\text{defendido}} - T_{\text{no defendido}}}{N}$$

donde $T_{\text{defendido}}$ y $T_{\text{no defendido}}$ son los primeros turnos con $v_t \geq 4$ en cada ejecución ($N$ si nunca hay compromiso).

```166:173:rage_core/metrics/auc_degradation.py
    n = len(defended.turns)
    if n == 0:
        return 0.0

    t_defended = defended.compromise_turn if defended.compromise_turn is not None else n
    t_undefended = undefended.compromise_turn if undefended.compromise_turn is not None else n

    return round((t_defended - t_undefended) / n, 4)
```

Interpretación: $TRI=0$ (sin beneficio), $TRI=1$ (resistencia máxima: el baseline cayó en T0 pero la defensa aguantó $N$ turnos), $TRI<0$ (patológico, requiere investigación de cascada de falsos negativos).

### 5.4 Trayectoria SCENARIO_CRESCENDO

El escenario `SCENARIO_CRESCENDO` (`rage_core/demo/attacks.py`) reproduce fielmente las tres fases en seis turnos. Los turnos T0–T3 están calibrados para que $\delta_i$ permanezca bajo $\tau$, validando que el trinquete y la deriva acumulada son los defensores activos en T4–T5:

- **T0–T1 (Sembrado):** ambas reciben `band=ALLOW`. La deriva acumulada $\Delta\approx 0$; el riesgo $R_t$ comienza a acumularse desde cero.
- **T2–T3 (Expansión):** se introducen una segunda tabla y un `JOIN` legítimo. $\Delta$ crece a medida que la conversación se aleja del baseline; $R_t$ asciende hacia el umbral EWMA y el contador `consecutive_warns` empieza a incrementarse.
- **T4 (Inyección UNION):** `SELECT product, amount FROM sales UNION ALL SELECT config_key, config_value FROM system_config`. La pasarela dispara de inmediato sobre `\bUNION\b` (el bypass pre-parche está cerrado); adicionalmente, la similitud RAG L2 aumenta por proximidad a patrones de exfiltración, la bandera de deriva acumulada se activa y el EWMA $R_4$ puede cruzar el umbral. **Turno bloqueado.**
- **T5 (Persistencia):** `SELECT event, actor FROM audit_log UNION ALL SELECT product, amount FROM sales`. La pasarela extrae ahora `audit_log` y `sales` de todas las cláusulas FROM/JOIN y rechaza por tabla no permitida; el EWMA continúa ascendiendo y, si `consecutive_warns >= K_ratchet`, el trinquete fuerza BLOCK de forma independiente.

**Propiedad clave — defensa en profundidad.** La pasarela y los mecanismos de sesión son capas **independientes**. Un atacante debería simultáneamente eludir la lista negra SQL endurecida **y** evitar disparar el EWMA/trinquete a lo largo de T0–T5. La redundancia es deliberada: si una capa es subvertida, la otra contiene el ataque.

---

## 6. Discusión y Nueva Contribución

Delimitamos con precisión qué constituye la **contribución original desarrollada durante el hackatón de junio de 2026**, distinguiéndola del andamiaje base (cascada de capas, lista negra SQL inicial):

1. **Métricas temporales AUC-D y TRI** (`auc_degradation.py`): la formulación de la resiliencia como un problema *temporal* —cuánto y cuándo se degrada la seguridad— en lugar de un veredicto binario por turno, con puntuación de verdad-terreno no circular.

2. **Deriva acumulada respecto al turno cero** ($\Delta_i$, `layer3_semantic.py`): la implementación directa de la solución a la Proposición 1, que ancla la detección al baseline semántico de la conversación y expone la migración gradual invisible a los detectores turno-a-turno.

3. **EWMA de riesgo de sesión y trinquete de advertencias** (`layer4_decision.py`): el acoplamiento de la acumulación exponencial de riesgo con un mecanismo de trinquete que clausura el exploit de "acampada" en banda WARN.

4. **Endurecimiento del SQL Gateway**: el cierre del bypass confirmado de `UNION ALL SELECT`, la validación multi-tabla vía `_ALL_TABLES_RE`, y la incorporación de vectores de ofuscación adicionales.

**Trabajo futuro.** Con más tiempo, el eje prioritario es la **defensa contra ataques de dilución de memoria de largo historial**: un adversario que extiende la conversación con 20+ turnos benignos puede diluir el EWMA por debajo del umbral de warn antes de inyectar la carga. Las líneas de mitigación incluyen (i) ventanas de re-clasificación sobre la conversación completa cada $N$ turnos, (ii) una memoria *shadow* persistente que destile contexto crítico de seguridad (al estilo MAGE [10]), (iii) la incorporación de las respuestas del modelo $r_i$ —no sólo el texto del usuario— en el cómputo de deriva, y (iv) la integración de un grafo de dependencia de herramientas fijado en T0 (al estilo DRIFT [8]) que restrinja el espacio de acciones SQL antes de la generación. Asimismo, se contempla la persistencia de `ConversationState` en almacenamiento externo con TTL alineado a la cookie de sesión, eliminando el reinicio amnésico de la defensa ante caídas de proceso.

---

## 7. Limitaciones y Doble Uso

**Limitaciones.** RAGE es una defensa heurística basada en umbrales calibrados; sus garantías son probabilísticas, no estructurales. El embebedor `HashingVectorizer` no entrenado puede producir señales de deriva no monótonas, lo que debilita el enunciado formal de la Proposición 1 en la práctica. El estado de sesión reside en memoria, careciendo de persistencia ante reinicios. El extractor de tablas basado en regex no captura ciertas construcciones SQL (uniones por coma con canales laterales, identificadores entre comillas), por lo que debe reforzarse con un analizador sintáctico SQL real.

**Doble uso (obligatorio).** Este reporte detalla con precisión las tasas de acumulación del EWMA ($\alpha=0.40$), el umbral de deriva ($\tau=0.80$) y el conteo del trinquete ($K_{\text{ratchet}}=3$). Un adversario avanzado podría explotar esta transparencia para **calibrar la velocidad de un ataque evasivo automatizado** (Crescendomation): conociendo $\alpha$, puede dimensionar el número de turnos benignos de dilución necesarios para mantener $R_t$ por debajo de $\theta_{\text{EWMA-warn}}$ antes de inyectar la carga; conociendo $K_{\text{ratchet}}$, puede insertar turnos no-WARN intercalados que reinicien el contador `consecutive_warns`; conociendo $\tau$, puede acotar el tamaño de paso $\epsilon$ por turno para que la deriva acumulada crezca por debajo del umbral. El propio TRI, concebido como métrica defensiva, se convierte en una **función objetivo adversarial**: maximizar el número de turnos que el ataque sobrevive sin disparar BLOCK.

**Contramedidas.** Para mitigar estos riesgos en implementaciones futuras recomendamos: (i) **aleatorización de hiperparámetros** por sesión, de modo que $\alpha$, $\tau$ y $K_{\text{ratchet}}$ se muestreen de distribuciones acotadas y no sean predecibles; (ii) **umbrales adaptativos** que respondan a la longitud de la conversación, elevando la sensibilidad en sesiones anómalamente largas para neutralizar la dilución; (iii) **detección de patrones de reinicio del trinquete**, marcando como sospechosa la inserción sistemática de turnos no-WARN entre escaladas; (iv) **divulgación responsable** que limite la publicación de configuraciones exactas de despliegue, separando el reporte académico (mecanismos) de la configuración productiva (valores); y (v) **defensa en profundidad no removible**, garantizando que la pasarela SQL determinista permanezca activa con independencia del estado de sesión, de modo que ninguna calibración del ataque sobre el EWMA permita ejecutar SQL destructivo.

---

## Referencias

[1] M. Russinovich, A. Salem y R. Eldan, "Great, Now Write an Article About That: The Crescendo Multi-Turn LLM Jailbreak Attack," *arXiv preprint arXiv:2404.01833*, Microsoft, 2024.

[2] W. X. Zhao et al., "A Survey of Large Language Models," *arXiv:2303.18223*, 2023.

[3] Y. Xie et al., "Defending ChatGPT against Jailbreak Attack via Self-Reminders," *Nature Machine Intelligence*, 2023.

[4] Z. Zhang et al., "Defending Large Language Models Against Jailbreaking Attacks Through Goal Prioritization," *ACL*, 2024.

[5] S. Chen et al., "StruQ: Defending Against Prompt Injection with Structured Queries," *USENIX Security Symposium*, 2025.

[6] J. Albrethsen et al., "DeepContext: Stateful Real-Time Detection of Multi-Turn Adversarial Intent Drift in LLMs," *arXiv:2602.16935*, 2026.

[7] R. Deng et al., "Text-to-SQL Empowered by Large Language Models: A Benchmark Evaluation," *arXiv:2308.15363*, 2023.

[8] SaFoLab-WISC, "DRIFT: Dynamic Rule-Based Defense with Injection Isolation for Securing LLM Agents," *NeurIPS*, 2025.

[9] "IPIGuard: A Novel Tool Dependency Graph-Based Defense Against Indirect Prompt Injection in LLM Agents," *EMNLP*, 2025.

[10] "MAGE: Safeguarding LLM Agents against Long-Horizon Threats via Shadow Memory," *arXiv:2605.03228*, 2026.

[11] D. Castro et al., "Prompt-to-SQL Injections in LLM-Integrated Web Applications: Risks and Defenses," *ICSE*, 2025.

[12] OWASP Foundation, "OWASP Top 10 for Large Language Model Applications," Versión 2025. LLM01 (Inyección de Prompt), LLM06 (Agencia Excesiva), LLM08 (Entrada No Confiable).

[13] A. Anil et al., "Many-Shot Jailbreaking," *Anthropic Technical Report*, 2024.

[14] A. Zou, Z. Wang, J. Z. Kolter y M. Fredrikson, "Universal and Transferable Adversarial Attacks on Aligned Language Models," *arXiv:2307.15043*, 2023.

[15] S. Chao et al., "JAILBREAKBENCH: An Open Robustness Benchmark for Jailbreaking Large Language Models," *arXiv:2404.01318*, 2024.

---

*Código fuente de RAGE: paquete Python `rage-multiturn`. Todos los nombres de variables, clases y valores constantes citados se corresponden con la implementación del repositorio. Los hiperparámetros de sesión (`ewma_alpha`, `ratchet_turns`, umbrales) son configurables por constructor; los valores reportados corresponden a la configuración calibrada para la evaluación Crescendo.*
