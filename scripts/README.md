# Scripts index

Run all commands from the **repository root**.

## Daily use

| Script | Purpose |
|--------|---------|
| `check_setup.sh` | Verify repo layout (`rage_core/`, `pyproject.toml`) |
| `run-tests.sh` | 233 pytest regression tests |
| `validate-all.sh` | Full pre-release check (tests + benchmarks + PDF) |
| `run-demo.sh` | Research demo (`rage-demo`) |
| `run-product-demo.sh` | Track A product chat (`rage-product-demo`) |
| `run-support-chat.sh` | IT support interactive chat |
| `run-profile-chat.sh` | **Deprecated** — use `run-product-demo.sh` |
| `run-bench-generalization.sh` | Security holdout benchmark (~80% recall) |
| `run-bench-product.sh` | Track B product benchmark |
| `run-bench-live.sh` | Live benchmark with LLM judge |
| `run-bench-multi-live.sh` | Multi-turn live benchmark |
| `generate_submission_pdf.sh` | Build Global South PDF from `draft_submission.md` |
| `setup-env.sh` | Optional `.env` with model URLs only (no API secrets) |

## Maintenance (regenerate datasets / analysis)

Only needed when changing holdout data or running research scripts:

| Script | Purpose |
|--------|---------|
| `build_eval_generalization.py` | Rebuild `kb/eval_generalization/` |
| `build_eval_product.py` | Rebuild `kb/eval_product/` |
| `build_eval_practice.py` | Rebuild `kb/eval_practice/` |
| `build_eval_similar.py` | Rebuild `kb/eval_similar/` |
| `build_eval_open_v3.py` | Rebuild `kb/eval_open_v3/` |
| `build_holdout_scenarios_extended.py` | Extended scenario holdout |
| `build_holdout_scenarios_comparison.py` | Comparison holdout |
| `calibrate_eval_generalization.py` | Calibrate generalization recall |
| `probe_generalization_phrasing.py` | Phrasing probes |
| `run_ablation.py` / `run-ablation.sh` | Layer ablation |
| `analyze_bench.py` | Analyze Track B JSON output |

See [rage_core/kb/README.md](../rage_core/kb/README.md) for which dataset each benchmark uses.
