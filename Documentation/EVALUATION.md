# RAGE — Evaluation Methodology (read before citing results)

This document states **what the numbers actually measure**. Required reading for paper authors and reviewers.

## Three evaluation layers

| Layer | What | CI |
|-------|------|-----|
| **Contract tests** (`pytest`) | Gateway, L1–L4, metrics math, dataset integrity | `./scripts/run-tests.sh` |
| **Official security holdout** (`eval_locked_v1`) | Frozen labels; metrics computed at runtime; snapshot regression | `tests/test_benchmark_locked.py` + `./scripts/run-bench-locked.sh` |
| **Dev / legacy sets** (`eval_practice`, `eval_generalization`, …) | Tuning and experiments — **not** the official cited metric | `pytest -m dev_eval` (excluded from default CI) |

## Official metric: `eval_locked_v1`

- **Dataset:** `rage_core/kb/eval_locked_v1/` — frozen JSON + `MANIFEST.json` (SHA256 integrity).
- **Policy:** Do not edit cases after freeze; do not tune L1/L2 thresholds against this set.
- **Mode (baseline):** L1+L2, no LLM judge (`--fast`), single + multi-turn combined (52 turns).
- **Regression:** `benchmarks/baseline_locked_v1.json` — CI fails if metrics drift beyond tolerance without an explicit baseline update (`scripts/update_benchmark_baseline.py --write`).
- **No target recall band** — the number is whatever the pipeline scores on the frozen set (baseline at freeze: **100% recall, 0 FP** on 52 cases after removing legacy “FN expected” prompts).

Legacy `eval_generalization` (~80% calibrated recall) remains in the repo for history only.

## Benchmark vs demo pipeline

| Path | Ratchet | Block decision | LLM agent |
|------|---------|----------------|-----------|
| **Benchmark** (`rage-bench`) | OFF | `access_policy` | None — text classifier only |
| **Demo** (`rage-demo`) | ON | `access_policy` + gateway | **Simulated** victim |

**Implication:** Holdout recall is **detection on labeled text**, not Attack Success Rate (ASR) against a live GPT-4/Claude agent.

## What pytest means (default CI)

Regression tests for code contracts. **Passing ≠ 100% attack detection on unseen real-world prompts.**

Includes `test_benchmark_locked.py`: 0 FP on benign + snapshot match to baseline.

## Paper claims vs code (known gaps)

1. **Simulated agent** in demo — defense is real; victim LLM is not.
2. **Ratchet** applies in demo, not in benchmark metrics.
3. **Locked v1** is an internal frozen holdout, not an external benchmark like JailbreakBench.
4. **No published baselines** vs LlamaGuard / Rebuff in automated CI.

## Recommended citations

- ✅ “Frozen holdout `eval_locked_v1`: X% recall, 0% FP (L1+L2, commit …)” — use value from `baseline_locked_v1.json`
- ✅ “231+ automated regression tests (contract + locked snapshot)”
- ✅ “Crescendo scenario blocked at gateway + policy layer”
- ❌ “Calibrated ~80% recall band in CI” (removed)
- ❌ “End-to-end LLM ASR reduced to X%” (not measured)

## Reproduce

```bash
./scripts/run-tests.sh -q
./scripts/run-bench-locked.sh
uv run python scripts/update_benchmark_baseline.py --eval-set locked_v1 --combined --fast
./scripts/validate-all.sh
```

Dev-only calibrated sets: `uv run pytest tests/ -m dev_eval`
