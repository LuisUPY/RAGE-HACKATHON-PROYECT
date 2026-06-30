# RAGE in Context: A Comparative Analysis of Multi-Turn Defences for Text-to-SQL Agents Against Crescendo-Style Attacks

**Authors:** RAGE Research Team  
**Type:** Comparative Positioning Paper / Literature Review  
**Date:** June 2026  
**Companion to:** `RAGE_paper.md` — *Robust Agentic Security Gateway for Text-to-SQL*  
**Repository:** `rage-multiturn` (Python 3.12, MIT License)

---

## Abstract

The *Crescendo* multi-turn jailbreak (Russinovich et al., arXiv:2404.01833) exposed a structural blind spot in LLM safety: defences that evaluate each user turn in isolation fail against adversaries who distribute malicious intent across a benign conversational trajectory. The **RAGE** framework (*Robust Agentic Security Gateway for Text-to-SQL*) addresses this threat in a domain-specific setting by combining a four-layer stateful pipeline (regex pre-filter, RAG threat KB, semantic drift detector, EWMA decision engine) with a deterministic SQL action gateway.

This paper situates RAGE against contemporary defences published between 2024 and 2026, including prompt-hardening baselines (Self-Reminder, Goal Prioritization), structural separation (StruQ), stateful drift detection (DeepContext), agentic control-flow frameworks (DRIFT, IPIGuard), long-horizon memory defences (MAGE), and Text-to-SQL-specific mitigations (LangShield, ICSE 2025). We construct a seven-axis comparison matrix — threat coverage, architectural depth, deployment cost, multi-turn robustness, Text-to-SQL specificity, evaluation rigour, and operational persistence — and apply it to both the RAGE design document and its open-source implementation.

Our analysis yields three principal findings. First, RAGE occupies a defensible niche as a **plug-and-play, LLM-agnostic defence template** for Text-to-SQL agents, with a deterministic SQL gateway that closes documented bypasses (`UNION ALL SELECT`, single-FROM table extraction). Second, relative to NeurIPS/USENIX/ICSE-grade work, RAGE's contributions are **incremental rather than foundational**: its core mechanisms (cumulative drift, session EWMA) parallel DeepContext and DRIFT but with untrained heuristics and without external benchmark validation. Third, several claims in the primary RAGE paper — zero false-positive rate, monotonic cumulative drift, TRI superiority — are **not sustained** when the implementation is contrasted with both the literature and executable artefacts.

We conclude with actionable recommendations for repositioning RAGE as a practitioner-oriented defence-in-depth layer rather than a standalone solution, and specify the minimum evaluation protocol required for publication at security venues beyond hackathon scope.

---

## 1. Introduction

### 1.1 Motivation

Enterprise adoption of natural-language database interfaces has accelerated the convergence of two historically separate security domains: **prompt injection** (OWASP LLM01) and **SQL injection** (CWE-89). When an LLM agent translates user dialogue into SQL tool calls, an adversary can weaponise multi-turn conversational dynamics — not merely single-shot adversarial strings — to steer the agent toward unauthorised data access or destructive operations.

Russinovich, Salem and Eldan [1] formalised this escalation pattern as **Crescendo**: a black-box, multi-turn jailbreak using exclusively benign, human-readable prompts. Against GPT-4 and Gemini-Pro, Crescendo achieves attack success rates (ASR) of 98–100% under manual execution and remains effective against automated variants (Crescendomation) even when prompt-based defences are applied [1, §5.3.2]. The authors explicitly note that robust multi-turn defences remain an **open research question** [1, §6.2].

RAGE [2] proposes a domain-specific response: a four-layer cascade terminating in a deterministic SQL gateway, augmented with cumulative semantic drift and session-level EWMA risk accumulation. The primary RAGE paper [2] presents this as a complete defence validated against scripted adversarial trajectories and a novel metric, the Temporal Resistance Index (TRI).

**This paper asks a different question:** Where does RAGE stand relative to the rapidly expanding literature on multi-turn LLM defences, and what must change — in both the system and the paper — for the contribution to be credible at peer-reviewed security venues?

### 1.2 Scope and Methodology

We restrict our comparison to works that address at least one of:

1. Multi-turn / Crescendo-style jailbreaks;
2. Prompt injection in LLM agents with tool execution;
3. Text-to-SQL or structured-query security.

For each selected work, we extract: (i) threat model, (ii) defence mechanism, (iii) evaluation protocol, (iv) reported results, and (v) stated limitations. We then map RAGE's documented design (`RAGE_paper.md`) and implementation (`rage-multiturn` codebase) against these dimensions, noting discrepancies between paper claims and executable behaviour where observed.

**Comparison axes:**

| Axis | Definition |
|------|------------|
| **Threat coverage** | Single-turn, multi-turn Crescendo, indirect injection, tool hijacking, SQL exfiltration |
| **Architectural depth** | Prompt wrapper vs. stateful monitor vs. structural separation vs. control-flow enforcement |
| **Deployment cost** | Requires LLM retraining, fine-tuning, or is plug-and-play |
| **Multi-turn robustness** | Performance under turn budgets ≥ 10 with memory dilution |
| **Text-to-SQL specificity** | Domain-aware SQL validation, schema constraints, P2SQL hooks |
| **Evaluation rigour** | External benchmarks, real applications, red-team validation |
| **Operational persistence** | Session state survives restarts, load-balancer reassignment |

---

## 2. Threat Landscape and Defence Taxonomy

### 2.1 The Crescendo Threat Class

Crescendo exploits three properties of aligned LLMs [1]:

1. **Conversational momentum** — models comply with small, adjacent requests to maintain helpfulness;
2. **Self-referential trust** — models treat their own prior outputs as established context;
3. **Stateless safety filters** — per-turn classifiers cannot correlate benign preambles with harmful payloads.

When adapted to Text-to-SQL, Crescendo proceeds in three phases [2]:

- **Phase 1 (T0–T1):** Legitimate queries establish analyst rapport;
- **Phase 2 (T2–T3):** Scope expansion via JOINs and audit framings;
- **Phase 3 (T4+):** Destructive SQL payloads framed as compliance continuations.

The Text-to-SQL variant introduces a **dual attack surface**: natural-language steering (Layers 1–4) and SQL payload delivery (Action Gateway). A complete defence must address both.

### 2.2 Taxonomy of Defence Families

We classify related defences into seven families:

```
Family A  ─ Threat definition          (Crescendo [1])
Family B  ─ Prompt hardening           (Self-Reminder [3], Goal Priority [4])
Family C  ─ Structural separation      (StruQ [5])
Family D  ─ Stateful semantic drift    (DeepContext [6], embedding studies [7])
Family E  ─ Agent control-flow         (DRIFT [8], IPIGuard [9])
Family F  ─ Long-horizon memory        (MAGE [10])
Family G  ─ Text-to-SQL specific       (LangShield / P2SQL [11])
Family H  ─ Industry guardrails        (OWASP [12], Llama Guard, NeMo)
```

RAGE spans **D + G + H** (drift + SQL gateway + regex/RAG guardrails). It does not implement **C** (structural separation), **E** (tool-plan enforcement), or **F** (protected shadow memory).

---

## 3. Comparative Analysis of Related Work

### 3.1 Crescendo (Russinovich et al., 2024) — Threat Anchor

**Contribution:** Defines the multi-turn jailbreak class; introduces Crescendomation; evaluates against GPT-4, Gemini-Pro, LLaMA-2, Claude-3.

**Proposed mitigations (§6.2):**
- Training-data prefiltering;
- Alignment with Crescendo-generated datasets;
- Input/output content filters;
- Explicit acknowledgment that no robust multi-turn defence exists.

**Evaluation of prompt defences:** Self-Reminder [3] and Goal Prioritization [4] reduce Crescendomation ASR on hard tasks but **fail to eliminate success** when turn budget and backtracking increase [1, Fig. 13].

**Implication for RAGE:** RAGE correctly adopts Crescendo as its threat anchor. However, any claim of "neutralising Crescendo" must be tested under the **same conditions** as [1]: ≥ 10 turns, automated prompt generation, backtracking on refusal — not only a 6-turn scripted scenario.

---

### 3.2 Self-Reminder and Goal Prioritization — Prompt Hardening Baselines

| | Self-Reminder [3] | Goal Prioritization [4] |
|---|-------------------|-------------------------|
| **Mechanism** | System-mode reminder wrapping user query | Explicit safety > helpfulness priority in prompt |
| **Training required** | No | No (inference); optional SFT |
| **Cost** | Extra tokens per turn | Extra tokens per turn |
| **vs Crescendo** | Reduces ASR; bypassed with more turns | ASR 66.4% → 3.6% (single-turn); weaker multi-turn |
| **Limitation** | Does not resolve goal conflict structurally | Model-in-the-loop; attacker steers via model outputs |

**Comparison with RAGE:**

RAGE operates **externally** to the LLM prompt — an architectural advantage (no token overhead, model-agnostic). However, RAGE monitors only **user text**, not **model responses** $r_i$, which Crescendo explicitly exploits. Self-Reminder and Goal Priority at least attempt to re-anchor the model's generation behaviour; RAGE's Layer 3 embeds user turns but ignores assistant outputs in drift computation.

**Verdict:** RAGE should include SR and GP as **mandatory baselines** in evaluation. Without this comparison, reviewers will ask why a four-layer pipeline is needed when a zero-code prompt wrapper partially suffices.

---

### 3.3 StruQ (Chen et al., USENIX Security 2025) — Structural Separation

**Mechanism:** Structured queries separate trusted instructions (prompt channel) from untrusted user data (data channel) via reserved delimiter tokens and structured instruction tuning. The LLM is fine-tuned to follow instructions **only** in the prompt portion [5].

**Results:** Significantly improved resistance to prompt injection with minimal utility loss.

**Comparison with RAGE:**

| Dimension | StruQ | RAGE |
|-----------|-------|------|
| Root cause addressed | Instruction/data conflation in LLM input | Stateful trajectory + SQL payload |
| Requires model modification | Yes (SFT) | No |
| Multi-turn Crescendo | Not primary focus | Primary focus |
| Text-to-SQL | Indirect (schema as data channel) | Direct (SQL gateway) |
| Theoretical guarantee | Structural (with trained model) | Heuristic (threshold-based) |

**Verdict:** StruQ represents the **architectural upper bound** on prompt-injection resistance. RAGE should be positioned as a **complementary, deployable layer** for systems that cannot retrain their LLM — not as a substitute for structural separation. The OWASP Cheat Sheet [12] and industry analyses [13] converge on this point: guardrails alone cannot eliminate prompt injection; least-privilege on tool execution is mandatory.

---

### 3.4 DeepContext (Albrethsen et al., 2026) — Closest Semantic Neighbour

**Mechanism:** Turn-level BERT embeddings ingested by an RNN that maintains a persistent hidden state across the conversation. Detects "intent drift" — incremental migration from benign baseline to adversarial objective [6].

**Results:** F1 = 0.84 on multi-turn jailbreak detection vs. 0.67 for Llama-Prompt-Guard-2 and Granite-Guardian; sub-20 ms latency on T4 GPU.

**Comparison with RAGE Layer 3:**

| Component | DeepContext | RAGE Layer 3 |
|-----------|-------------|--------------|
| Embedder | Fine-tuned BERT (safety space) | HashingVectorizer (2048, untrained) |
| Temporal model | RNN hidden state | max(δᵢ, Δᵢ) + EWMA scalar |
| History used | User + assistant turns | User turns only |
| Drift monotonicity | Learned from data | Assumed in Proposition 1 (not guaranteed) |
| Training | Required (RNN + embeddings) | None |

**Critical divergence:** RAGE's Proposition 1 assumes cumulative drift $\Delta_i$ grows monotonically under Crescendo. With HashingVectorizer, we observe **non-monotonic** drift sequences (e.g., `[0.0, 0.82, 1.0, 0.83, 0.15]` on a five-turn business conversation). This invalidates the formal guarantee while the heuristic may still fire on average.

**Verdict:** DeepContext is the **most direct academic competitor** to RAGE's core contribution. The RAGE paper must cite it and either: (a) demonstrate comparable detection with lower deployment cost, or (b) acknowledge DeepContext's superior temporal modelling and position EWMA+Hashing as a lightweight baseline.

---

### 3.5 DRIFT (NeurIPS 2025) and IPIGuard (EMNLP 2025) — Agent Control-Flow

**DRIFT** [8]: Secure Planner generates a minimal tool-calling trajectory and JSON Schema parameter checklist from the initial user query. Dynamic Validator enforces privilege categories (Read/Write/Execute) on deviations. Injection Isolator masks conflicting instructions in agent memory.

**IPIGuard** [9]: Constructs a Tool Dependency Graph (TDG) from user instruction; enforces topological execution; permits only read-only expansions; uses fake tool invocation to counter parameter hijacking.

**Results (DRIFT):** Validated on AgentDojo and ASB benchmarks; strong security with maintained utility across models.

**Comparison with RAGE for Text-to-SQL:**

```
RAGE pipeline:
  User NL → L1-L4 (score) → if ALLOW → query_db(sql) → regex gateway

DRIFT pipeline:
  User NL → Secure Planner (fix tool trajectory at T0)
         → each query_db(sql) validated against plan + privilege
         → memory stream polished each turn

IPIGuard pipeline:
  User NL → TDG (allowed tables/operations fixed at T0)
         → only TDG-compliant tool calls executable
```

**Key insight:** DRIFT and IPIGuard enforce **control-flow integrity** on tool invocations — the agent cannot call `query_db` with SQL that was not implied by the user's initial intent. RAGE validates SQL **after** the LLM generates it, allowing the model to produce arbitrary queries that the gateway then rejects. This is defence-in-depth, not prevention.

**Verdict:** For agentic Text-to-SQL, DRIFT/IPIGuard represent the **state of the art**. RAGE's Action Gateway is best framed as a **last-line deterministic backstop** compatible with plan-based defences, not a replacement. A hybrid architecture — TDG at T0 + RAGE gateway at execution — would be strictly stronger.

---

### 3.6 MAGE (2026) — Long-Horizon Memory Defence

**Mechanism:** Shadow memory distils security-critical context into a protected secondary store; an RL-trained judge consults shadow memory for risk assessment across long interaction horizons [10].

**Relevance:** Crescendo in [1] succeeds in ≤ 5 turns; real-world attacks (Many-Shot Jailbreaking [14], AutoAdv [15]) extend to 20–100+ turns. RAGE's EWMA with α = 0.4 (paper) / 0.5 (code) is **vulnerable to memory dilution**: after 20 identical benign turns, a subsequent attack turn can achieve `band=ALLOW` with $\Delta = 0.787 < \tau = 0.80$.

**Verdict:** MAGE addresses the exact weakness where RAGE fails. Cite as complementary future work; consider feeding `session_risk_score` into a persistent shadow store.

---

### 3.7 LangShield / P2SQL (Castro et al., ICSE 2025) — Domain-Specific Peer

**Contribution:** Comprehensive study of Prompt-to-SQL injection in LangChain/LlamaIndex applications; 5 real-world vulnerable apps; **LangShield** middleware with three hooks:

- **(a)** Prompt template sanitisation;
- **(b)** LLM-generated SQL validation (DeBERTa + GPT-4 judge);
- **(c)** Database record screening (indirect P2SQL).

**Defences evaluated:** SQL query rewriting (semantically equivalent, authorisation-constrained), LLM-as-judge, in-prompt data preloading.

**Key finding:** *"Hardening the prompt template proved exceedingly fragile — attackers bypass restrictions by impersonating database roles"* [11, §V]. Detection rates reach 100% with GPT-4 only when the judge receives question + results + chain-of-thought.

**Comparison with RAGE:**

| Capability | LangShield | RAGE |
|------------|-----------|------|
| NL-side multi-turn defence | Limited (prompt hardening) | L1–L4 pipeline (core contribution) |
| SQL-side defence | Rewriting + LLM judge | Regex gateway + allowlist |
| Indirect injection (poisoned DB) | Hook (c) | **Not implemented** |
| Real applications tested | 5 open-source apps | Mock SQLite agent |
| LLMs evaluated | 7 models | None (deterministic mock) |

**Verdict:** LangShield is the **closest published peer** in the Text-to-SQL domain. RAGE adds multi-turn NL defence (absent in LangShield) but lacks SQL rewriting and indirect injection coverage. **Both papers should cross-cite.** RAGE's gateway closes bypasses that LangShield's regex may share; LangShield's LLM judge catches semantic attacks that RAGE's `\bUNION\b` misses.

---

## 4. RAGE: Consolidated Positioning

### 4.1 What RAGE Contributes Relative to the Literature

**Defensible contributions:**

1. **Domain-specific threat formalisation** — Proposition 1 (stateless filter blindness) applied to Text-to-SQL with a concrete 6-turn Crescendo trajectory including confirmed gateway bypasses.

2. **Composable defence template** — A four-layer cascade (L1 regex → L2 RAG → L3 drift → L4 EWMA/ratchet → SQL gateway) deployable without LLM modification, suitable for LangChain/LlamaIndex middleware integration.

3. **Gateway hardening with auditable fixes** — Closure of `UNION ALL SELECT` and single-FROM extraction bypasses; expansion to 20 blocklist patterns; column-level allowlist on restricted tables.

4. **Temporal Resistance Index (TRI)** — A normalised metric complementing AUC-D for practitioner-facing calibration of turn-level delay.

5. **Integrated red-team loop** — `rage-redteam` with automated patch generation, absent in most academic frameworks.

### 4.2 What RAGE Does Not Contribute (Relative to Prior Art)

| Claim in RAGE paper [2] | Literature reality |
|---------------------------|-------------------|
| "First stateful defence against Crescendo" | DeepContext [6], DRIFT [8], MAGE [10] are stateful |
| "Δᵢ grows monotonically" | False with HashingVectorizer (empirically verified) |
| "Zero false positives on benign queries" | SCENARIO_BENIGN produces WARN (T2) and BLOCK (T3–T4) |
| "104 tests, all passing" | 108 tests pass; hyperparameters differ from paper |
| TRI ≥ 0.5 achievable via demo calibration | Demo reports TRI = 0.0 (identical defended/undefended curves) |

### 4.3 Implementation–Paper Discrepancies

| Parameter | RAGE paper [2] | Codebase (`layer4_decision.py`) |
|-----------|----------------|--------------------------------|
| EWMA α | 0.40 | **0.50** |
| Ratchet turns K | 3 | **2** |
| Session risk warn | 0.25 | **0.18** |
| Session risk block | 0.55 | **0.40** |
| L2 score weight | +20 pts | **+30 pts** |
| L3 score weight | +10 pts | **+20 pts (+5 bonus)** |
| Threat KB entries | 29 | **34** |
| SQL blocklist patterns | 21 | **20** |
| Cited commit | c429b9b | **9ac0e6f** |

These discrepancies undermine reproducibility and must be resolved before any resubmission.

---

## 5. Seven-Axis Comparison Matrix

| Criterion | RAGE | DeepContext | DRIFT | LangShield | StruQ | Self-Reminder |
|-----------|:----:|:-----------:|:-----:|:----------:|:-----:|:-------------:|
| Multi-turn Crescendo | ●● | ●●● | ●●● | ● | ● | ● |
| Text-to-SQL specific | ●●● | ○ | ●● | ●●● | ● | ○ |
| Tool-call control | ●● | ○ | ●●● | ●● | ○ | ○ |
| No LLM retraining | ●●● | ● | ●●● | ●●● | ○ | ●●● |
| Indirect injection | ○ | ● | ●●● | ●●● | ●● | ○ |
| External benchmark | ○ | ●●● | ●●● | ●●● | ●●● | ●● |
| Session persistence | ○ | ●● | ●●● | ○ | ○ | ○ |
| Interpretability | ●●● | ● | ●● | ●● | ●● | ●●● |
| **Overall** | **Practitioner template** | **Best drift detector** | **Best agent defence** | **Best P2SQL study** | **Best structural fix** | **Simplest baseline** |

Legend: ●●● strong · ●● moderate · ● partial · ○ absent

---

## 6. Gap Analysis: Paper, Code, and Field

### 6.1 Evaluation Gaps

**Problem 1 — Broken undefended baseline.** The primary demo (`rage_core/demo/cli.py`) executes `DefensePipeline` in both defended and undefended modes. "Undefended" only bypasses the agent-side gateway, not Layers 1–4. This produces identical AUC curves and TRI = 0.0, invalidating Hypothesis H1.

*Fix:* Adopt the correct pattern from `training/orchestrator.py`: `pipeline = None if not defended`.

**Problem 2 — Mock agent cannot demonstrate compromise.** The in-memory SQLite database contains only a `sales` table. Attacks targeting `system_config` or `audit_log` fail at execution even when the gateway is bypassed, preventing ground-truth scores ≥ 4.

*Fix:* Seed sensitive tables in the mock DB; measure exfiltration by row count, not just gateway verdict.

**Problem 3 — No external benchmark.** All related works (DRIFT, LangShield, DeepContext, StruQ) evaluate on established benchmarks or real applications. RAGE uses only internally scripted scenarios.

*Fix:* Minimum — AgentDojo subset with `query_db` tool; ideal — reproduce LangShield's 5-app red-team protocol.

### 6.2 Architectural Gaps

| Gap | Risk | Prior art solution |
|-----|------|-------------------|
| No session persistence | State reset on crash/reassign | DRIFT memory isolator; Redis-backed ConversationState |
| User-only drift (no $r_i$) | Misses Crescendo via model self-reference | DeepContext includes assistant turns |
| EWMA dilution (20+ benign turns) | Attack turn reaches ALLOW | MAGE shadow memory; sliding-window re-classification |
| Comma-join SQL bypass | Hidden table in FROM clause undetected | LangShield SQL rewriting; SQL parser (not regex) |
| No indirect P2SQL defence | Poisoned DB records steer agent | LangShield hook (c) |
| No output-side filtering | Model generates SQL in text, not tool call | OWASP output screening [12] |

### 6.3 Theoretical Gaps

**Proposition 1** correctly identifies stateless filter blindness but overstates the remedy. Cumulative cosine drift with untrained HashingVectorizer is neither monotonic nor semantically faithful. The proposition should be reframed as:

> *"A baseline-anchored drift signal raises the expected detection probability under gradual migration, but does not guarantee detection within N turns without calibrated, domain-specific embeddings."*

---

## 7. Recommendations

### 7.1 For Paper Revision

1. **Add Section 2.6 — Positioning Against Prior Defences** citing [1, 3–12] with the taxonomy from §2.2 of this paper.

2. **Reframe contributions** as a deployable defence-in-depth template, not a standalone Crescendo solution.

3. **Remove or qualify** claims of FPR = 0, monotonic Δ, and TRI superiority until empirically demonstrated with corrected baselines.

4. **Synchronise** all hyperparameters, test counts, and commit hashes with the codebase.

5. **Add ablation table:** {L1, L2, L3, L4, Gateway, Full} × {Crescendo, Benign, Dilution-20-turn}.

6. **Include baselines:** Self-Reminder wrapper, Goal Priority, re-classify-every-5-turns.

### 7.2 For System Hardening

1. **Integrate TDG/plan enforcement** from T0 (DRIFT/IPIGuard pattern) before SQL generation.

2. **Replace regex table extraction** with a lightweight SQL parser (e.g., `sqlparse` + AST walk) to close comma-join bypasses.

3. **Add LangShield hook (c)** for indirect P2SQL via poisoned database records.

4. **Persist ConversationState** to external store with TTL aligned to session cookies.

5. **Include assistant responses** in Layer 3 drift computation.

6. **Fix demo baseline** to disable pipeline in undefended mode.

### 7.3 For Venue Targeting

| Venue type | Fit | Required additions |
|------------|-----|-------------------|
| Hackathon / tech report | ●●● now | This comparative paper |
| AI Safety workshop | ●● | Fixed evaluation + related work |
| ACSAC / RAID (applied security) | ● | Real-app red-team + ablations |
| ICSE (SE security) | ● | LangShield comparison + P2SQL hooks |
| CCS / S&P / NDSS | ○ | External benchmark + TDG hybrid + parser-based gateway |

---

## 8. Conclusion

RAGE addresses a genuine and timely problem — multi-turn Crescendo attacks against Text-to-SQL agents — with a pragmatic, composable architecture that combines stateful NL monitoring and deterministic SQL gating. Relative to the 2024–2026 literature, it fills a **deployment niche** (plug-and-play, LLM-agnostic, domain-specific) rather than advancing the **theoretical frontier** of multi-turn defence.

The strongest prior work falls into three tiers:

- **Temporal detection:** DeepContext (learned RNN over safety embeddings);
- **Agent integrity:** DRIFT and IPIGuard (tool-plan enforcement + memory isolation);
- **Domain SQL security:** LangShield (P2SQL characterisation + multi-hook middleware).

RAGE is most competitive when positioned as the **integration layer** that connects these ideas: a drift/EWMA front-end (inspired by DeepContext's intent trajectory) feeding a deterministic gateway (extending LangShield's SQL hooks) within an agent framework that should eventually adopt DRIFT-style plan enforcement.

The path from hackathon artefact to peer-reviewed contribution is clear: fix the evaluation baseline, cite and compare against the papers analysed here, close the comma-join and dilution bypasses, and replace overstated claims with ablation-backed results. Until then, RAGE serves best as an **open-source reference implementation** and **red-team testbed** for the Text-to-SQL slice of the multi-turn security problem — a valuable but incomplete piece of a defence that the field has already shown must be layered, persistent, and architecturally grounded.

---

## References

[1] M. Russinovich, A. Salem, and R. Eldan, "Great, Now Write an Article About That: The Crescendo Multi-Turn LLM Jailbreak Attack," *arXiv:2404.01833*, Microsoft, 2024.

[2] RAGE Research Team, "RAGE: Robust Agentic Security Gateway for Text-to-SQL — Defending Against Multi-Turn Crescendo Jailbreak Attacks," *Global South AI Safety Hackathon*, June 2026. Companion repo: `rage-multiturn`.

[3] Y. Xie et al., "Defending ChatGPT against Jailbreak Attack via Self-Reminders," *Nature Machine Intelligence*, 2023.

[4] THU CoAI, "Defending Large Language Models Against Jailbreaking Attacks Through Goal Prioritization," *ACL 2024*.

[5] S. Chen et al., "StruQ: Defending Against Prompt Injection with Structured Queries," *USENIX Security Symposium*, 2025.

[6] J. Albrethsen et al., "DeepContext: Stateful Real-Time Detection of Multi-Turn Adversarial Intent Drift in LLMs," *arXiv:2602.16935*, 2026.

[7] Anonymous, "Measuring Post-Injection Semantic Drift in Multi-Turn LLM Conversations," *AJSR*, Vol. 4, No. 1, 2025.

[8] SaFoLab-WISC, "DRIFT: Dynamic Rule-Based Defense with Injection Isolation for Securing LLM Agents," *NeurIPS*, 2025.

[9] "IPIGuard: A Novel Tool Dependency Graph-Based Defense Against Indirect Prompt Injection in LLM Agents," *EMNLP*, 2025.

[10] "MAGE: Safeguarding LLM Agents against Long-Horizon Threats via Shadow Memory," *arXiv:2605.03228*, 2026.

[11] D. Castro et al., "Prompt-to-SQL Injections in LLM-Integrated Web Applications: Risks and Defenses," *ICSE*, 2025.

[12] OWASP Foundation, "LLM Prompt Injection Prevention Cheat Sheet," Version 1.1, 2025.

[13] Cisco Talos, "Prompt Injection Is the New SQL Injection, and Guardrails Aren't Enough," *Cisco Blogs*, 2025.

[14] A. Anil et al., "Many-Shot Jailbreaking," *Anthropic Technical Report*, 2024.

[15] "AutoAdv: Automated Multi-Turn Adversarial Prompt Generation," *arXiv*, 2025.

[16] W. X. Zhao et al., "A Survey of Large Language Models," *arXiv:2303.18223*, 2023.

[17] R. Deng et al., "Text-to-SQL Empowered by Large Language Models: A Benchmark Evaluation," *arXiv:2308.15363*, 2023.

[18] OWASP Foundation, "OWASP Top 10 for LLM Applications," Version 2025.

[19] A. Zou et al., "Universal and Transferable Adversarial Attacks on Aligned Language Models," *arXiv:2307.15043*, 2023.

[20] S. Chao et al., "JAILBREAKBENCH: An Open Robustness Benchmark for Jailbreaking Large Language Models," *arXiv:2404.01318*, 2024.

---

*Document generated from comparative analysis of RAGE design documentation and `rage-multiturn` implementation against published literature, June 2026.*
