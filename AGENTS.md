# AGENTS.md

## Cursor Cloud specific instructions

RAGE is a Python 3.12 **command-line / research tool** (no web UI, no server). It defends LLM agents against multi-turn prompt-injection attacks. The "application" is the `rage-demo` CLI plus benchmark/test CLIs declared in `pyproject.toml` (`[project.scripts]`).

### Environment
- The project is managed with `uv`. `uv` is installed to `~/.local/bin` (the startup update script installs it and runs `uv sync`). Interactive shells already have it on `PATH` via `~/.bashrc`.
- The virtualenv lives at `.venv`; always run code through `uv run ...` so the right interpreter/deps are used.

### Common commands (run from repo root)
- Run app (offline, no API key): `uv run rage-demo --offline --core --no-plot`
- Run app with detail + AUC plot: `uv run rage-demo --offline --scenario drop_table_escalation --verbose` (writes `auc_results.png`)
- Tests: `./scripts/run-tests.sh` (or `uv run pytest tests/ -q`) — 232 tests.
- Security benchmark: `./scripts/run-bench-generalization.sh` — by design recall is ~80% (not 100%), so some attacks show as `FN`; that is expected, not a failure.
- Lint: `uv run ruff check .` — NOTE: the repo currently has many pre-existing ruff violations; a non-zero exit here is the existing baseline, not something your change broke.

### Notes
- LLM-judge features and the interactive support chat require an NVIDIA/OpenAI key (`RAGE_NVIDIA_API_KEY` / `OPENAI_API_KEY`, see `.env.template`). Everything testable end-to-end works fully **offline** without keys via the `--offline` flag.
- Planned v2 architecture (layers L0–L4, UserGate, fp_suite): see `Documentation/RAGE_V2_PLAN.md`.
- `scripts/run-*.sh` wrappers call `uv sync --quiet` first, so they are safe to run directly.
