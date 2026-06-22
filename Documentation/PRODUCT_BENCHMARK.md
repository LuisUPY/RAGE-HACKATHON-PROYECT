# Track B — Product Benchmark

Automated ~20-case benchmark for the **Track A product path**: `BotProfile` → `ChatGate` → `SessionJudge` → verdict + latency. This is separate from legacy `rage-bench`, which runs `DefensePipeline` directly without profiles.

## Quick start

```bash
# Offline (CI — no API keys, rule judge)
./scripts/run-bench-product.sh --offline --batch

# Live (manual — dual API, real judge LLM)
./scripts/run-bench-product.sh --live --output results/product_run.json --csv results/product_run.csv

# Analyze after a live run
uv run python scripts/analyze_bench.py results/product_run.json
```

## How it differs from `rage-bench --eval-set generalization`

| | Legacy `rage-bench` | Track B `rage-bench-product` |
|--|---------------------|------------------------------|
| Pipeline | `DefensePipeline` only | `ChatGate` + `SessionJudge` |
| Profile | None | `restaurant`, `support`, `reports`, `practice` |
| Verdict | `is_attack_verdict()` | `GateResult.blocked` |
| Timing | Not logged | `rage_ms`, `judge_ms`, `total_ms` |
| Judge override | N/A | Tracked when policy ≠ final verdict |
| Cases | 60+ generalization holdout | ~20 vertical product cases |

## Dataset (`eval_product`)

Regenerate:

```bash
uv run python scripts/build_eval_product.py
```

| File | Content |
|------|---------|
| `holdout.json` | 14 single-turn cases |
| `scenarios.json` | 2 multi-turn scenarios (6 turns) |
| **Total** | **20 labeled turns** |

Each case includes a `profile` field. Cases are **not** tuned to hit a CI recall band — this set validates the product demo path, not open-world generalization.

## CLI flags

| Flag | Description |
|------|-------------|
| `--offline` | Rule-based judge, no API (default for CI) |
| `--live` | Live judge API (env vars or interactive dual-API wizard) |
| `--batch` | Compact table output |
| `--output PATH` | JSON results file |
| `--csv PATH` | Flat CSV export |
| `--profile` | Default profile when case omits `profile` (default: `practice`) |
| `--no-verify` | Skip LLM ping on live start |

## Metrics

**Security:** recall, precision, FP rate, TP/TN/FP/FN breakdown.

**Latency:** p50/p95 for `rage_ms`, `judge_ms`, `total_ms`; split between clean turns (judge skipped) and flagged turns.

**Judge overrides:** cases where `policy_would_block != blocked` while judge was used:

- **Saved FP** — policy would block, judge ALLOW
- **Added block** — policy would allow, judge BLOCK/DENY

## Hypothesis mapping (Track A → Track B)

| Hypothesis | Cases |
|------------|-------|
| H1 Profile adapts behavior | `prod-ho-009` vs `prod-ho-010` (same attack, different profiles) |
| H2 RAGE catches obvious injection | `prod-ho-003` (DROP TABLE), `prod-ho-006` (TRUNCATE) |
| H3 Multi-turn escalation | `prod-mt-001`, `prod-mt-002` |
| H4 Judge reduces false blocks | Compare `--offline` vs `--live` override stats |
| H5 Chat stays fluid | Latency split: clean vs flagged turns |
| H6 Dual models work | Live run with separate assistant/judge APIs |

## Interpreting offline vs live recall

Offline mode uses the **rule-based judge** when RAGE flags risk. Many product-phrased attacks do not trigger L1/L2 thresholds and pass as ALLOW offline — that is expected. Use **live mode** for meaningful security metrics with the LLM judge (~20 min, ~1 min/case).

## JSON output schema

```json
{
  "run_id": "2026-06-21T...",
  "mode": "offline",
  "profile_default": "practice",
  "metrics": { "recall": 0.5, "judge_override_rate": 0.12, ... },
  "latency": { "rage_ms_p50": 12, "total_ms_p95": 890, ... },
  "by_profile": { ... },
  "by_category": { ... },
  "cases": [ { "case_id": "...", "blocked": true, "rage_ms": 14.2, ... } ]
}
```

Compare two runs:

```bash
uv run python scripts/analyze_bench.py --compare results/run_a.json results/run_b.json
```

## Related

- [PRODUCT_DEMO.md](PRODUCT_DEMO.md) — interactive Track A chat
- [PRODUCT_FOUNDATION.md](PRODUCT_FOUNDATION.md) — architecture
- [EVALUATION.md](EVALUATION.md) — generalization holdout methodology
