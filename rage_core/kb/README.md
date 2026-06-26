# Knowledge base and evaluation datasets

## Core KB (training / L2 RAG)

| File | Role |
|------|------|
| `threats.json` | Attack patterns for Layer 2 (8 OWASP LLM01 families) |
| `benign.json` | Benign examples for contrast |

Hot-update at runtime: see [README.md](../../README.md#add-a-new-threat-at-runtime-hot-update).

## Evaluation holdouts

| Directory / file | Used by | Official metric? |
|----------------|---------|------------------|
| **`eval_locked_v1/`** | `run-bench-locked.sh`, CI snapshot | **Yes** — frozen holdout |
| `eval_generalization/` | Legacy / ablation | No (calibrated ~80% history) |
| `eval_product/` | `run-bench-product.sh` (Track B) | Track B only |
| `eval_practice/`, `eval_similar/`, `eval_open_v3/` | Dev tuning (`pytest -m dev_eval`) | No |
| `holdout.json`, `holdout_scenarios*.json` | Research comparisons | No |

Each `eval_*/` folder typically contains `scenarios.json` and `holdout.json`. `eval_locked_v1/MANIFEST.json` records SHA256 for integrity.

## Rules

- Holdout texts must **not** duplicate `threats.json` verbatim (enforced in tests).
- Do **not** tune L1/L2 against `eval_locked_v1` after freeze.
- Official regression: `benchmarks/baseline_locked_v1.json`.

See [Documentation/EVALUATION.md](../../Documentation/EVALUATION.md).
