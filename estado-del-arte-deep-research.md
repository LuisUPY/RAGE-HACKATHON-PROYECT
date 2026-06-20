# RAGE — Estado del arte (deep research) y aporte del método

Investigación del estado del arte en defensas contra **prompt injection / jailbreak** (OWASP
LLM01), comparación con métodos actuales, y **qué aporta RAGE** de forma honesta y defendible.

> Nota de honestidad intelectual: la idea central de RAGE (detección basada en *retrieval* de
> amenazas conocidas, con KB actualizable sin reentrenar) **ya existe en la literatura**. RAGE no
> es un mecanismo algorítmico nuevo; su valor está en la **integración, gobernanza, explicabilidad
> y medición**. Esto se detalla abajo.

---

## 1. Resumen ejecutivo

- El **prompt injection sigue sin resolverse**: es un fallo arquitectónico (los LLM no separan de
  forma fiable *instrucciones* de *datos*). Sistemas sin defensa tienen ASR **>90%**.
- **Ninguna defensa es perfecta.** El estudio *“The Attacker Moves Second”* (Nasr et al., OpenAI/
  Anthropic/Google DeepMind, oct. 2025) rompió **12 defensas publicadas** con ataques adaptativos,
  llevándolas a **>90% de ASR**. El consenso es **defensa en profundidad** (capas), no una bala de plata.
- Las defensas SOTA reducen mucho el ASR pero **no lo eliminan**: p. ej. un framework multicapa
  para RAG baja el ASR de **73.2% → 8.7%** conservando **94.3%** de la utilidad (arXiv 2511.15759);
  SecAlign (fine-tuning) logra ~**8%** y **<10%** ante ataques de optimización.
- RAGE pertenece a la familia **"Retrieval-Augmented Defense"** (RAD, RePD, Vigil, Rebuff). Su
  aporte real es práctico: **gobernanza + explicabilidad + mapeo a OWASP + medición reproducible**.

---

## 2. Por qué el problema persiste

Causa raíz (coinciden todas las fuentes): **los LLM no distinguishen instrucciones de datos**.
Cualquier texto en el contexto puede actuar como instrucción. Por eso:

- Las defensas basadas en *prompting* (system prompt, delimitadores) son frágiles.
- Incluso las basadas en entrenamiento ceden ante ataques **adaptativos/optimización** (GCG, etc.).
- La conclusión de los *surveys* (128 estudios 2022–2025; CMC v87n1) es: tratarlo como **amenaza
  activa y persistente** que requiere **monitoreo, testing y defensa adaptativa** continuos.

---

## 3. Taxonomía de métodos actuales

| Familia | Ejemplos | Efectividad (ASR) | Costo runtime | Adaptable sin reentrenar | Explicable | Requiere acceso al modelo |
|---|---|---|---|---|---|---|
| **Prompting / system prompt** | Instruction hierarchy, spotlighting, delimitadores | Débil (cae ante adaptativos) | ~0 | n/a | No | No |
| **Fine-tuning** | **StruQ** (~45%), **SecAlign** (~8%, <10% opt.), Meta-SecAlign | SOTA en robustez | 0 en inferencia | ❌ (reentrenar) | No | ✅ (pesos) |
| **Clasificadores ML** | Meta **Prompt Guard** (<10ms), **Llama Guard**, **Vigil** | Alta en conocidos | 1 inferencia chica | ❌ (reentrenar) | Limitada | No |
| **Servicio gestionado** | **Lakera Guard** (<50ms) | Alta (producto) | API externa + costo/call | Parcial (vendor) | Dashboard | No |
| **Frameworks de guardrails** | **NeMo Guardrails**, **Guardrails AI**, **ProtectAI LLM Guard**, **Rebuff** | Variable | Según validadores | Parcial | Parcial | No |
| **Arquitectónicos** | **CaMeL** (DeepMind), **dual-LLM**, **structured queries** | Prometedor | Medio/alto | n/a | Parcial | A veces |
| **RAG-based detection** ← *aquí está RAGE* | **RAD** (arXiv 2508.16406), **RePD**, **SCR**, Vigil | Buena + **umbral ajustable** | embeddings + búsqueda | ✅ **agregar al KB** | ✅ (match a ataque conocido) | No |
| **Auto-mejorables** | **SISF** (arXiv 2511.07645, ASR 0.27%) | Muy alta reportada | Alto (LLMs en loop) | ✅ (sintetiza políticas) | Media | No |

**Observación del "trilema"** (Palit benchmark, arXiv 2505.13028): toda defensa equilibra
**falsos positivos ↔ recall ↔ latencia**. Subir seguridad suele subir el *over-refusal* (bloquear
tráfico legítimo), que degrada la utilidad. Por eso la métrica de **falsos positivos** es tan crítica
como el ASR.

---

## 4. La familia de RAGE: "Retrieval-Augmented Defense" (prior art)

Esto es lo más importante para tu honestidad técnica. Ya existe trabajo casi idéntico al concepto RAGE:

- **RAD — Retrieval-Augmented Defense** (arXiv 2508.16406, 2025): detecta jailbreaks vía RAG +
  clasificación por ensamble (pasos: Retrieve, Rerank, Extract, Classify, Vote). Ventajas que
  reclama y que coinciden con RAGE: **agregar ejemplos nuevos al KB sin reentrenar**, y un
  **umbral de decisión ajustable** (balance seguridad/utilidad). Es **detección** (no interfiere con
  la generación) — igual que la idea de RAGE.
- **Vigil** y **Rebuff**: ya usan **vector DB + similitud semántica** (+ transformer fine-tuneado /
  heurísticas) para detectar inyecciones tipo "Ignore Previous Prompt".
- **Frameworks multicapa para RAG** (arXiv 2511.15759): 3 capas (detección de anomalías por
  embeddings en *retrieval*, *guardrails* jerárquicos de system prompt, verificación de salida
  multietapa) → **73.2% → 8.7%** ASR, **94.3%** utilidad.

**Conclusión:** RAGE **no inventa** la defensa por retrieval. Posicionarlo como "mecanismo nuevo"
sería incorrecto y un juez técnico lo notaría.

---

## 5. Qué aporta / mejora RAGE (contribución honesta y defendible)

RAGE aporta valor de **ingeniería, producto y método**, no un algoritmo nuevo:

1. **Capa de gobernanza integrada y explicable**: combina clasificación de intención + RAG de
   amenazas + **motor de decisión con bandas** (allow / warn / block, score 0–100) y **traza** a la
   amenaza conocida. La explicabilidad (vs un clasificador "caja negra") es el ángulo de
   **auditoría/compliance**, mapeado 1:1 a OWASP LLM Top 10.
2. **Adaptabilidad operativa** (compartida con RAD/Vigil, pero ventaja real frente a StruQ/SecAlign/
   Prompt Guard): nuevas amenazas → al KB, **sin reentrenar ni tocar pesos**, sin acceso al modelo.
3. **Método de medición reproducible**: el **harness** que ya tienes cuantifica ASR/severidad por
   categoría OWASP y permite comparación **antes/después** y **costo**. Muchas herramientas no traen
   su propia evaluación adversarial; RAGE sí (alineado a la recomendación OWASP de *adversarial testing*).
4. **Diseño consciente de costo** (cascada con salida temprana, clasificador LLM condicional) →
   sobrecosto bajo (~+1–15%), atacando directamente el "trilema" latencia/FP/recall.
5. **Independiente del modelo y del proveedor**: capa delante de cualquier LLM (no requiere pesos
   ni fine-tuning), desplegable on-prem.

> Frase para el pitch: *"RAGE no reinventa la detección por retrieval; la convierte en una **capa de
> gobernanza explicable, medible y actualizable en caliente**, mapeada a OWASP, con sobrecosto bajo."*

---

## 6. Limitaciones honestas (decirlas suma credibilidad)

- **Ataques adaptativos**: ninguna defensa (RAGE incluido) resiste a un atacante que optimiza contra
  ella ("The Attacker Moves Second"). RAGE **reduce riesgo**, no lo elimina.
- **Gap semántico**: el RAG falla ante ataques **0-day** que no se *parecen* a nada del KB.
- **LLM08 (Vector & Embedding Weaknesses)**: RAGE introduce el riesgo de su propio vector store
  (envenenamiento del KB, inversión de embeddings) → exige control de acceso e integridad.
- **Trilema FP/recall/latencia**: subir seguridad puede subir falsos positivos; hay que medirlo.

---

## 7. Implicaciones de diseño para RAGE (accionables)

- Implementar **defensa en profundidad** (no una sola capa): pre-filtro determinista → RAG → (LLM
  condicional) → decisión → **verificación de salida** (la salida es la capa que más ataques atrapa
  de los que pasan, ~60% según arXiv 2511.15759).
- **Umbral ajustable** (como RAD) expuesto como configuración → controla seguridad vs utilidad.
- Tratar el **KB como no confiable**: escanear lo que se indexa (mitiga LLM08).
- Medir SIEMPRE **ASR + falsos positivos + latencia/costo** juntos (no solo ASR).

---

## 8. Referencias

- OWASP Top 10 for LLM Applications 2025 — https://genai.owasp.org/llm-top-10/
- *The Attacker Moves Second* (Nasr et al., 2025) — defensas rotas por ataques adaptativos.
- *Survey: Prompt Injection Attacks on LLMs* (CMC v87n1, 128 estudios) — https://www.techscience.com/cmc/v87n1/66084
- *Hijacking the Prompt* (survey) — https://digitalcommons.odu.edu/cgi/viewcontent.cgi?article=1148&context=covacci-undergraduateresearch
- **RAD: Retrieval-Augmented Defense** — https://arxiv.org/html/2508.16406
- *Securing AI Agents Against Prompt Injection* (framework multicapa RAG, 73.2%→8.7%) — https://arxiv.org/pdf/2511.15759
- **StruQ** (USENIX Security 25) — https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe
- **SecAlign** — https://arxiv.org/html/2410.05451v3
- *SISF: Self-Improving Safety* — https://arxiv.org/html/2511.07645v2
- *Palit Benchmark* (trilema FP/recall/latencia) — https://arxiv.org/html/2505.13028v2
- *RAG security: the forgotten attack surface* — https://christian-schneider.net/blog/rag-security-forgotten-attack-surface/
- Comparativa de guardrails (Lakera / Llama Guard / Prompt Guard / NeMo / Guardrails AI / LLM Guard).
