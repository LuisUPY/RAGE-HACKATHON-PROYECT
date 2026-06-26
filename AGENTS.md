# AGENTS.md

## Cursor Cloud specific instructions

RAGE is a Python 3.12 **command-line / research tool** (no web UI, no server). It defends LLM agents against multi-turn prompt-injection attacks. The "application" is the `rage-demo` CLI plus benchmark/test CLIs declared in `pyproject.toml` (`[project.scripts]`).

### Environment
- The project is managed with `uv`. `uv` is installed to `~/.local/bin` (the startup update script installs it and runs `uv sync`). Interactive shells already have it on `PATH` via `~/.bashrc`.
- The virtualenv lives at `.venv`; always run code through `uv run ...` so the right interpreter/deps are used.

### Common commands (run from repo root)
- **Cheat sheet:** [QUICKSTART.md](../QUICKSTART.md)
- Run app (offline, no API key): `uv run rage-demo --offline --core --no-plot`
- Run app with detail + AUC plot: `uv run rage-demo --offline --scenario drop_table_escalation --verbose` (writes `auc_results.png`)
- Tests: `./scripts/run-tests.sh` (or `uv run pytest tests/ -q`) — 233+ tests.
- Security benchmark: `./scripts/run-bench-locked.sh` — frozen `eval_locked_v1`; metrics at runtime vs `benchmarks/baseline_locked_v1.json` (no calibrated recall band).
- **v2 fp_suite:** `uv run pytest tests/fp_suite/ -q` — must stay 0 CONTAIN on benign corpus.
- Lint: `uv run ruff check .` — NOTE: the repo currently has many pre-existing ruff violations; a non-zero exit here is the existing baseline, not something your change broke.

### Notes
- LLM-judge features and the interactive support chat require an NVIDIA/OpenAI API key, **prompted at runtime** (not read from `.env`). Everything testable end-to-end works fully **offline** without keys via the `--offline` flag. For non-interactive CI, export `RAGE_LLM_API_KEY` or `OPENAI_API_KEY` in the job environment.
- Planned v2 architecture (layers L0–L4, UserGate, fp_suite): see `Documentation/RAGE_V2_PLAN.md`. Implementation lives under `rage_core/v2/`.
- `scripts/run-*.sh` wrappers call `uv sync --quiet` first, so they are safe to run directly.
