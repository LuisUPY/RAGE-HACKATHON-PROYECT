# Automated test suite

RAGE uses **three separate evaluation layers**. Do not conflate them.

## 1. Regression suite (`pytest`) — code contracts

**Command:** `./scripts/run-tests.sh` or `uv run pytest tests/ -v`

**231 tests** in default CI (`dev_eval` tests excluded). They verify:

| Module | Focus |
|--------|--------|
| `test_gateway.py` | SQL blocklist, UNION ALL regression, tool allowlist |
| `test_benchmark.py` | Dataset integrity, evaluator math, multi-turn structure |
| `test_benchmark_locked.py` | **Official** frozen holdout: 0 FP + snapshot regression |
| `test_layers.py` | L1–L4 pipeline, drift, ratchet |
| `test_semantic_filter.py` | Cumulative drift, sanitizer |
| `test_auc_metric.py` | AUC-D, TRI, hypotheses H1/H4 |
| `test_access_policy.py` | Multi-turn verdict thresholds |
| `tests/v2/test_user_gate.py` | UserGate + EscalationJudge |
| `tests/fp_suite/` | 0 CONTAIN on benign corpus (CI gate) |
| `tests/test_benchmark_locked_v2.py` | Frozen `eval_locked_v1` regression (v2) |
| `test_product_benchmark.py` | Track B product dataset + evaluator |
| `test_demo.py` | Demo orchestrator smoke |
| `test_env_loader.py` | .env loading skips API secrets |
| `test_openai_compat.py` | LLM/judge client config |

**What “all tests pass” means:** contracts + frozen holdout snapshot match.  
**What it does NOT mean:** 100% attack detection on unseen production prompts.

### Dev-only calibrated tests

```bash
uv run pytest tests/ -m dev_eval
```

Legacy recall targets on `threats.json`, `holdout`, `open_v3`, `similar` — for tuning only.

## 2. Official security holdout — `eval_locked_v1`

**Command:** `./scripts/run-bench-locked.sh`

- Frozen dataset with `MANIFEST.json` integrity checks.
- Metrics computed at runtime; regression vs `benchmarks/baseline_locked_v1.json`.
- **No calibrated recall band** in CI.

## 3. Product benchmark (Track B)

**Command:** `./scripts/run-bench-product.sh --offline --batch`

~20 labeled cases on Track A path. Separate from `eval_locked_v1`.

## CI

```bash
./scripts/run-tests.sh -q
./scripts/run-bench-locked.sh
./scripts/run-bench-product.sh --offline --batch
```

See also [QUICKSTART.md](../QUICKSTART.md) and [Documentation/EVALUATION.md](../Documentation/EVALUATION.md).
