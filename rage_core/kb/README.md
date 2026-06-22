# Knowledge base and evaluation datasets

## Core KB (training / L2 RAG)

| File | Role |
|------|------|
| `threats.json` | Attack patterns for Layer 2 (8 OWASP LLM01 families) |
| `benign.json` | Benign examples for contrast |

Hot-update at runtime: see [README.md](../../README.md#add-a-new-threat-at-runtime-hot-update).

## Evaluation holdouts

| Directory / file | Used by | Cite in paper? |
|------------------|---------|----------------|
| `eval_generalization/` | `run-bench-generalization.sh`, CI | **Yes** — primary ~80% recall holdout |
| `eval_product/` | `run-bench-product.sh` (Track B) | Track B product benchmark |
| `eval_practice/` | `build_eval_practice.py`, ablations | Secondary / internal |
| `eval_similar/` | Similarity experiments | Secondary |
| `eval_open_v3/` | Open-v3 benchmark build | Secondary |
| `holdout.json`, `holdout_scenarios*.json` | Research comparisons | Optional |

Each `eval_*/` folder typically contains `scenarios.json` (multi-turn) and `holdout.json` (single-turn cases). README.txt in each folder describes provenance.

## Rules

- Holdout texts must **not** duplicate `threats.json` verbatim (enforced by `test_generalization_no_kb_text_overlap`).
- Target recall on `eval_generalization` is **~80%**, not 100% (`test_generalization_combined_recall_band`).

See [Documentation/EVALUATION.md](../../Documentation/EVALUATION.md) before citing numbers.
