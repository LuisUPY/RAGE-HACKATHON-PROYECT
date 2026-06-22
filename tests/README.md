# Automated test suite

RAGE uses **two separate evaluation layers**. Do not conflate them.

## 1. Regression suite (`pytest`) — code contracts

**Command:** `./scripts/run-tests.sh` or `uv run pytest tests/ -v`

**232 automated tests** run on every change. They verify:

| Module | Focus |
|--------|--------|
| `test_gateway.py` | SQL blocklist, UNION ALL regression, tool allowlist |
| `test_benchmark.py` | Dataset integrity, **holdout recall band (~80%)**, multi-turn metrics |
| `test_layers.py` | L1–L4 pipeline, drift, ratchet |
| `test_semantic_filter.py` | Cumulative drift, sanitizer |
| `test_auc_metric.py` | AUC-D, TRI, hypotheses H1/H4 |
| `test_access_policy.py` | Multi-turn verdict thresholds |
| `test_chat_gate.py` | Track A ChatGate + session judge |
| `test_product_benchmark.py` | Track B product dataset + evaluator |
| `test_demo.py` | Demo orchestrator smoke |
| `test_ollama_client.py` | LLM client config |

**What “all tests pass” means:** the implementation matches its specified behavior.  
**What it does NOT mean:** 100% attack detection on unseen prompts.

## 2. Security benchmark — open-world holdout

**Command:** `./scripts/run-bench-generalization.sh`

- Holdout texts are **not copied from `threats.json`** (enforced by `test_generalization_no_kb_text_overlap`).
- Target recall is **~80%**, not 100% (`test_generalization_combined_recall_band` fails if recall > 85% or < 75%).
- **0% benign false positives** required.

This is the honest security metric for papers and demos.

## 3. Product benchmark (Track B)

**Command:** `./scripts/run-bench-product.sh --offline --batch`

~20 labeled cases on the Track A path (`BotProfile` → `ChatGate` → `SessionJudge`). Separate from generalization holdout.

## CI

```bash
./scripts/run-tests.sh -q
./scripts/run-bench-generalization.sh
./scripts/run-bench-product.sh --offline --batch
```

See also [QUICKSTART.md](../QUICKSTART.md) and [Documentation/EVALUATION.md](../Documentation/EVALUATION.md).
