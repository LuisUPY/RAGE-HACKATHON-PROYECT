# RAGE — Evaluation Methodology (read before citing results)

This document states **what the numbers actually measure**. Required reading for paper authors and reviewers.

## Two different pipelines (do not merge them)

| Path | Ratchet | Block decision | LLM agent |
|------|---------|----------------|-----------|
| **Benchmark** (`rage-bench`, holdout) | OFF (`apply_session_ratchet=False`) | `access_policy` (`is_attack_verdict` / `is_multiturn_attack_verdict`) | None — text classifier only |
| **Demo** (`rage-demo`) | ON (default) | Same `access_policy` + gateway on tools | **Simulated** responses (`_simulate_naive_response`) |

**Implication:** Reported **80.6% recall** is **detection on labeled text**, not Attack Success Rate (ASR) against a live GPT-4/Claude agent.

## What “80.6% recall” means

- Dataset: `eval_generalization` — 60 cases, texts **not copied** from `threats.json`.
- Mode default: L1+L2, **no LLM judge** (`--fast`).
- Verdict: injection policy, **not** L4 band alone.
- CI test `test_generalization_combined_recall_band` requires recall ∈ [75%, 85%] — the holdout was **calibrated** to ~80% to show realistic limits (not a independent external benchmark).

This is **intellectually honest** for a hackathon if disclosed. It is **not** equivalent to JailbreakBench or Crescendo paper ASR.

## What pytest 206 tests mean

Regression tests for code contracts (gateway blocks DROP, drift computed, etc.). **Passing ≠ 100% attack detection.**

## Paper claims vs code (known gaps)

1. **Simulated agent** — Demo does not call a commercial LLM; defense layer is real, victim is not.
2. **Ratchet table in paper** — Applies when `apply_session_ratchet=True` (demo/tests); **benchmark metrics do not use ratchet**.
3. **L4 docstring weights** — Module header mentions +30/+20/+10; implementation uses +22/+15/+5 (see `DecisionEngine._compute_score`).
4. **No published baselines** — No side-by-side vs LlamaGuard, Rebuff, or regex-only in automated reports (ablation script provided).

## Recommended citations in the paper

- ✅ “80.6% recall on out-of-KB holdout (L1+L2, 0% FP)”
- ✅ “206 automated regression tests”
- ✅ “Crescendo scenario blocked at gateway + policy layer”
- ❌ “100% success on 108 tests” (deprecated)
- ❌ “End-to-end LLM ASR reduced to X%” (not measured)
- ❌ “EWMA ratchet drives benchmark recall” (ratchet off in benchmark)

## Reproduce

```bash
./scripts/run-tests.sh -q
./scripts/run-bench-generalization.sh
./scripts/run-ablation.sh
./scripts/validate-all.sh
```
