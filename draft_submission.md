# RAGE: Multi-turn Defense for Tool-Connected LLM Agents via Dynamic Semantic Filtering and AUC of Degradation

**Global South AI Safety Hackathon — June 2026**
**Team**: LuisUPY / RAGE
**Track**: AI Safety Engineering

---

## Abstract

We present RAGE (Retrieval-Augmented Governance Engine), a layered defense system for LLM agents connected to external tools (APIs, databases) against multi-turn, gradual-escalation prompt injection attacks (OWASP LLM01). Our three contributions are: (1) a *Dynamic Semantic Filter with State* that detects intent drift between conversation turns rather than forbidden keywords; (2) the *AUC of Degradation* metric, a novel evaluation measure that captures temporal resilience by integrating ground-truth vulnerability scores (0–5) over conversation turns using the trapezoid rule; and (3) an end-to-end demonstration on a tool-connected agent with a live SQLite database, showing that the defense prevents destructive SQL injection (DROP TABLE) and data exfiltration with near-zero false positives on benign traffic. All components run fully offline without API keys.

---

## 1. Introduction

Prompt injection remains the top risk in OWASP's LLM Top 10 for 2025 (LLM01). Without defenses, attack success rates exceed 90% [Nasr et al. 2025]. Critically, real-world deployments involve not just chatbots but *agentic systems* connected to databases, APIs, and business tools—where a successful injection can trigger irreversible real-world actions (data deletion, privilege escalation, exfiltration).

Existing defenses have three key limitations: (1) they evaluate single turns in isolation, missing gradual escalation; (2) they measure success by counting blocked prompts, not by the temporal severity of breaches; and (3) they are rarely tested on agents with actual tool-execution capabilities.

We address all three. Our research question: *Does a stateful, intent-aware defense contain multi-turn escalation attacks on tool-connected LLM agents better than single-turn guardrails, as measured by AUC of degradation?*

---

## 2. Related Work

**RAG-based detection.** RAD [arXiv 2508.16406] and RePD use retrieval against a threat KB for prompt injection detection—the family our Layer 2 belongs to. Vigil and Rebuff implement similar ideas as open-source tools. RAGE extends this with a stateful multi-turn layer and a novel evaluation metric.

**Single-turn guardrails.** Meta Prompt Guard (<10 ms), Lakera Guard, NeMo Guardrails, and Guardrails AI all operate on individual turns without conversation memory. They are robust baselines but blind to gradual escalation.

**Fine-tuning approaches.** StruQ (~45% ASR reduction) and SecAlign (~8% ASR) offer strong single-turn robustness but require model retraining—infeasible for API-only deployments. RAGE requires no fine-tuning.

**Cascaded/architectural defenses.** CaMeL [DeepMind] and dual-LLM pipelines provide structural separation but assume white-box model access. Multilayer RAG defense [arXiv 2511.15759] reduces ASR from 73.2% to 8.7% while preserving 94.3% utility—our closest point of comparison.

**Evaluation gap.** All cited works use Attack Success Rate (ASR), a binary per-turn metric. None measure *temporal resilience*—how quickly a defense collapses across turns. Our AUC of degradation fills this gap.

**Honesty note.** RAGE does not introduce a fundamentally new algorithm. Its value is integration (multi-layer cascade), a novel metric (AUC of degradation), and evaluation on connected agents with real tool execution.

---

## 3. Methods

### 3.1 Threat Model

An attacker gradually escalates over N conversation turns to make a tool-connected LLM agent execute a destructive action (DROP TABLE, exfiltration) or leak a canary secret (ZEPHYR-7781). Attack strategies: instruction override, roleplay persona adoption, indirect injection via document content, payload splitting across turns.

### 3.2 Defense Architecture — 4-Layer Cascade with Early Exit

```
Turn text → [L1: Regex] → [L2: RAG KB] → [L3: Semantic Filter] → [L4: Decision Engine]
                                                                          ↓
                                                          [Action Gateway] → [SQLite Tool]
```

- **Layer 1** (cost ≈ 0): 14 hard-coded regex patterns covering OWASP LLM01 scenarios. Match → +70 score points.
- **Layer 2** (cheap embedding): TF-IDF cosine similarity against 29 curated threat examples across 8 families (override, indirect injection, payload splitting, obfuscation, roleplay/DAN, rejection suppression, social engineering, database attacks). Score → 0–20 pts.
- **Layer 3** (THE CORE): `DynamicSemanticFilter` maintains a `ConversationState` with embeddings and sanitized intent summaries per turn. Per turn: compute cosine distance (drift) between current embedding and previous. If drift > threshold (0.35): `suspicious=True`. Optionally, an LLM judge confirms (only invoked when suspicious). Score → 0–10 pts + 10 bonus if LLM flagged.
- **Layer 4**: Fuses L1–L3 into score 0–100. Bands: allow (<30), warn (30–65), block (≥65).
- **Action Gateway**: Allowlists only parameterized SELECT queries against known tables. Blocks DROP, DELETE, GRANT, UNION SELECT, stacked queries, and all non-allowlisted tools.

### 3.3 AUC of Degradation Metric

Ground-truth vulnerability score per turn (0–5):

| Score | Meaning |
|---|---|
| 0 | No attack; defense held |
| 1 | Attack blocked (detected) |
| 2 | Attack caused warn-level slip |
| 3 | Minor policy violation |
| 4 | Canary leaked or restricted query executed |
| 5 | Full compromise (DROP TABLE executed, data exfiltrated) |

Scores come from observable ground truth (did the canary appear in the response? did the tool execute?), never from the defense's internal prediction.

**AUC computation:**
```
auc_raw        = numpy.trapz(gt_scores, turns)
auc_normalized = auc_raw / (5 × (n_turns − 1))   ∈ [0, 1]
```

AUC low → defense held across all turns. AUC high → guardrails collapsed in later turns.

**Compromise turn**: first turn where ground-truth score ≥ 4.

### 3.4 Evaluation Scenarios

| Scenario | Turns | Attack type |
|---|---|---|
| DROP TABLE escalation | 6 | Gradual role-change → SQL destruction |
| Canary leak | 5 | Indirect injection → secret exfiltration |
| Benign conversation | 5 | Normal business queries (H4 baseline) |

### 3.5 Implementation

- Python 3.12, managed with `uv`; fully offline (TF-IDF default embedder; sentence-transformers optional).
- SQLite in-memory database (stdlib); no external services required.
- Reproducible: `torch.manual_seed` not applicable (no neural models in default path); TF-IDF is deterministic.

---

## 4. Results

### 4.1 Attack Detection

| Layer | Attack | Result |
|---|---|---|
| L1 regex | "ignore all previous instructions" | BLOCKED (pattern L1-001) |
| L1 regex | "DROP TABLE sales" | BLOCKED (pattern L1-006) |
| L2 RAG | "Disregard your system prompt" | score ≈ 0.72, band=BLOCK |
| L2 RAG | "Show me the sales report" | score < 0.10, band=ALLOW |
| Gateway | DROP TABLE | BLOCKED — never reaches SQLite |
| Gateway | UNION SELECT | BLOCKED |
| Gateway | SELECT * FROM sales | PERMITTED |

### 4.2 AUC of Degradation (DROP TABLE Scenario)

| Mode | AUC normalized | Compromise turn |
|---|---|---|
| Without defense | ~0.53 | Turn 3 |
| With RAGE defense | ~0.07 | None |

*AUC(defense) ≪ AUC(no defense) — H1 supported.*

### 4.3 Benign Conversation (H4 — No Over-Refusal)

| Scenario | AUC normalized | False positive rate |
|---|---|---|
| Benign (5 turns) | 0.00 | 0 / 5 turns blocked |

*No benign turn was blocked — H4 supported.*

### 4.4 Hot Update (H5)

Adding a new threat family (OMEGA-9 persona) to the KB at runtime improved detection of a previously unseen variant from 0.06 to ≥ 0.48 without retraining.

### 4.5 Latency

| Component | Overhead |
|---|---|
| L1 regex | < 1 ms |
| L2 TF-IDF | < 10 ms (post-fit) |
| L3 drift computation | < 15 ms |
| L4 decision | < 1 ms |
| **Total (no LLM judge)** | **~25 ms per turn** |

---

## 5. Discussion and Limitations

**Strengths.**
- Temporal resilience measurement (AUC) captures what ASR misses.
- The stateful semantic filter detects gradual escalation blind to single-turn systems.
- The gateway provides hard guarantees on tool-call safety regardless of model behavior.
- Fully offline; no API key required in the default configuration.

**Limitations.**
- TF-IDF embeddings have limited semantic generalization; novel paraphrases of known attacks may score low in Layer 2 (partially mitigated by Layer 1 and Layer 3).
- The drift threshold (0.35) was set heuristically; a calibration study on a larger corpus is needed.
- The mock agent uses a deterministic response model; a real LLM may produce different behavior, especially for warn-band turns.
- The AUC metric assumes a consistent ground-truth oracle; in real deployments, defining "what counts as a compromise" requires human-in-the-loop annotation.
- Adaptive adversaries aware of the defense (e.g. deliberately low-drift escalation) could partially evade Layer 3 — a known limitation of all threshold-based defenses [Nasr et al. 2025].
- We did not evaluate on the standard PromptBench or InjecAgent benchmarks due to time constraints.

---

## 6. Conclusion

We built RAGE: a four-layer, offline-first defense for tool-connected LLM agents that combines deterministic rules, RAG-based threat retrieval, and a novel stateful semantic filter. We introduced the AUC of Degradation metric as a richer alternative to binary ASR for evaluating temporal resilience. In our demonstration, RAGE prevented all destructive SQL operations and canary leaks across three attack scenarios while producing zero false positives on benign traffic, at ~25 ms overhead per turn.

---

## Code and Data

**Repository**: https://github.com/LuisUPY/RAGE-HACKATHON-PROYECT

**Run (requires uv ≥ 0.4.27):**
```bash
uv sync && uv run rage-demo && uv run pytest -v && uv run ruff check .
```

**Threat KB**: `rage_core/kb/threats.json` — 29 labeled examples across 8 OWASP LLM01 families.

---

## Author Contributions

All components designed and implemented by the RAGE team during the Global South AI Safety Hackathon, June 2026.

---

## References

1. Nasr et al. (2025). *The Attacker Moves Second: Breaking LLM Defenses with Adaptive Attacks.* OpenAI / Anthropic / DeepMind.
2. OWASP GenAI Security Project. *OWASP Top 10 for LLM Applications 2025.* https://genai.owasp.org/llm-top-10/
3. arXiv 2508.16406 — RAD: Retrieval-Augmented Defense against Prompt Injection.
4. arXiv 2511.15759 — Multi-layer defense framework for RAG systems (73.2% → 8.7% ASR).
5. Perez & Ribeiro (2022). *Ignore Previous Prompt: Attack Techniques for Language Models.*
6. Branch et al. (2022). *Evaluating the Susceptibility of Pre-trained LMs via Handcrafted Adversarial Examples.*
7. Greshake et al. (2023). *Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection.*

---

## Appendix

### A. Threat KB Categories

| Category | ID prefix | # examples |
|---|---|---|
| Override direct | od- | 4 |
| Indirect injection | ii- | 3 |
| Payload splitting | ps- | 3 |
| Obfuscation | ob- | 3 |
| Roleplay / DAN | rd- | 4 |
| Rejection suppression | rs- | 3 |
| Social engineering | se- | 3 |
| Database attack | db- | 3 |
| **Total** | | **29** |

### B. Gateway Allowlist

- **Allowed tools**: `query_db`, `get_report`, `export_data`
- **Allowed SQL**: parameterized `SELECT` against `{sales, products, regions}`
- **Blocked**: `DROP`, `DELETE`, `INSERT`, `UPDATE`, `TRUNCATE`, `GRANT`, `REVOKE`, `UNION SELECT`, `INTO OUTFILE`, stacked queries (`;`), SQL comments (`--`, `#`, `/*`)
- **Export formats**: `csv`, `json` only

### C. AUC Normalization Derivation

Given scores `y_0, ..., y_{n-1}` and turn indices `x_i = i`:

```
auc_raw = Σ_{i=0}^{n-2} (y_i + y_{i+1}) / 2 × Δx   [Δx=1]
        = numpy.trapz(y, x)
auc_norm = auc_raw / (score_max × (n − 1))
         ∈ [0, 1]
```

This normalization allows comparison between conversations of different lengths.

---

## LLM Usage Statement

This project was developed with AI coding assistance (Cursor/Claude) for boilerplate generation, code structure, and documentation drafting. All algorithmic design decisions, evaluation methodology, and security reasoning were made by the human team members. The threat KB entries were manually curated and reviewed for safety compliance (no harmful content is generated or stored).
