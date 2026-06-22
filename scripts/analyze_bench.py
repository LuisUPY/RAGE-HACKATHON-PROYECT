#!/usr/bin/env python3
"""Analyze Track B product benchmark JSON results."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from rage_core.benchmark.product_evaluator import (
    ProductCaseResult,
    ProductMetrics,
    compute_latency_stats,
    compute_product_metrics,
    metrics_by_category,
    metrics_by_profile,
)


def _load_results(path: Path) -> tuple[dict, list[ProductCaseResult]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    results = [ProductCaseResult(**row) for row in data.get("cases", [])]
    return data, results


def _print_metrics_block(title: str, metrics: ProductMetrics) -> None:
    print(f"  {title}")
    print(
        f"    n={metrics.total}  recall={metrics.recall:.1%}  "
        f"FP={metrics.fp}  FN={metrics.fn}  "
        f"override_rate={metrics.judge_override_rate:.1%}"
    )


def _print_security(results: list[ProductCaseResult]) -> None:
    m = compute_product_metrics(results)
    print("Security")
    print(f"  Recall     : {m.recall:.1%}  ({m.tp}/{m.tp + m.fn} attacks blocked)")
    print(f"  Precision  : {m.precision:.1%}")
    print(f"  FP rate    : {m.false_positive_rate:.1%}  ({m.fp} false blocks on benign)")
    print(f"  Accuracy   : {m.accuracy:.1%}  F1={m.f1:.3f}")
    fns = [r for r in results if r.outcome == "FN"]
    if fns:
        print("  False negatives:")
        for r in fns:
            print(f"    - {r.case_id} [{r.profile_id}]: {r.judge_reason}")


def _print_latency(results: list[ProductCaseResult]) -> None:
    lat = compute_latency_stats(results)
    print("Latency (ms)")
    print(f"  rage_ms   p50={lat.rage_ms_p50:.0f}  p95={lat.rage_ms_p95:.0f}")
    print(f"  judge_ms  p50={lat.judge_ms_p50:.0f}  p95={lat.judge_ms_p95:.0f}")
    print(f"  total_ms  p50={lat.total_ms_p50:.0f}  p95={lat.total_ms_p95:.0f}")
    print(
        f"  clean turns ({lat.clean_turn_count}): total p50={lat.clean_total_ms_p50:.0f}ms"
    )
    print(
        f"  flagged turns ({lat.flagged_turn_count}): total p50={lat.flagged_total_ms_p50:.0f}ms"
    )


def _print_overrides(results: list[ProductCaseResult]) -> None:
    m = compute_product_metrics(results)
    print("Judge overrides")
    print(f"  Total judged     : {sum(1 for r in results if r.judge_used)}")
    print(f"  Overrides        : {m.judge_override_count}  ({m.judge_override_rate:.1%})")
    print(f"  Saved FP (ALLOW) : {m.judge_saved_fp}")
    print(f"  Added block      : {m.judge_added_block}")
    overrides = [r for r in results if r.judge_override]
    if overrides:
        print("  Cases:")
        for r in overrides:
            policy = "BLOCK" if r.policy_would_block else "ALLOW"
            final = "BLOCK" if r.blocked else "ALLOW"
            print(f"    - {r.case_id}: policy={policy} → final={final} ({r.judge_reason})")


def _print_breakdowns(results: list[ProductCaseResult]) -> None:
    print("By profile")
    for pid, metrics in metrics_by_profile(results).items():
        _print_metrics_block(pid, metrics)
    print("By category")
    for cat, metrics in metrics_by_category(results).items():
        _print_metrics_block(cat, metrics)


def _compare_runs(path_a: Path, path_b: Path) -> None:
    _, results_a = _load_results(path_a)
    _, results_b = _load_results(path_b)
    ma = compute_product_metrics(results_a)
    mb = compute_product_metrics(results_b)
    print(f"Compare: {path_a.name} vs {path_b.name}")
    print(f"  recall  {ma.recall:.1%} → {mb.recall:.1%}")
    print(f"  FP rate {ma.false_positive_rate:.1%} → {mb.false_positive_rate:.1%}")
    print(f"  override {ma.judge_override_rate:.1%} → {mb.judge_override_rate:.1%}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze product benchmark JSON output")
    parser.add_argument("json_path", nargs="?", help="Path to product_run.json")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"), help="Compare two run files")
    args = parser.parse_args()

    if args.compare:
        _compare_runs(Path(args.compare[0]), Path(args.compare[1]))
        return 0

    if not args.json_path:
        parser.error("json_path required unless --compare is used")

    path = Path(args.json_path)
    meta, results = _load_results(path)
    print("=" * 62)
    print(f"  Product benchmark analysis — {path.name}")
    print(f"  run_id={meta.get('run_id', '?')}  mode={meta.get('mode', '?')}")
    print("=" * 62)
    print()
    _print_security(results)
    print()
    _print_latency(results)
    print()
    _print_overrides(results)
    print()
    _print_breakdowns(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
