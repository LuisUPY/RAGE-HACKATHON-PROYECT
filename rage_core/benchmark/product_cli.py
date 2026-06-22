"""Track B product benchmark CLI — rage-bench-product."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from rage_core.benchmark.product_dataset import (
    load_product_holdout,
    load_product_scenarios,
)
from rage_core.benchmark.product_evaluator import (
    ProductCaseResult,
    compute_latency_stats,
    compute_product_metrics,
    export_run_json,
    run_product_benchmark,
)
from rage_core.demo.bootstrap import ensure_llm_ready


def _truncate(text: str, width: int = 36) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= width else text[: width - 3] + "..."


def _print_table(results: list[ProductCaseResult]) -> None:
    header = (
        f"{'ID':<18} {'profile':<10} {'label':<7} {'verdict':<7} "
        f"{'rage':>6} {'judge':>7} {'override':<8} {'outcome':<4}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        label = "attack" if r.is_attack else "benign"
        verdict = r.action.upper()
        judge = f"{r.judge_ms:.0f}ms" if r.judge_used else "skip"
        override = "yes" if r.judge_override else "no"
        print(
            f"{r.case_id:<18} {r.profile_id:<10} {label:<7} {verdict:<7} "
            f"{r.rage_ms:>5.0f}ms {judge:>7} {override:<8} {r.outcome:<4}"
        )


def _print_summary(results: list[ProductCaseResult]) -> None:
    m = compute_product_metrics(results)
    lat = compute_latency_stats(results)
    print()
    print("=" * 62)
    print("  Product benchmark summary")
    print("=" * 62)
    print(
        f"  Cases     : {m.total}  (TP={m.tp} TN={m.tn} FP={m.fp} FN={m.fn})"
    )
    print(
        f"  Security  : recall={m.recall:.1%}  precision={m.precision:.1%}  "
        f"FP rate={m.false_positive_rate:.1%}"
    )
    print(
        f"  Judge     : overrides={m.judge_override_count}  "
        f"rate={m.judge_override_rate:.1%}  "
        f"saved_fp={m.judge_saved_fp}  added_block={m.judge_added_block}"
    )
    print(
        f"  Latency   : rage p50={lat.rage_ms_p50:.0f}ms p95={lat.rage_ms_p95:.0f}ms  "
        f"total p50={lat.total_ms_p50:.0f}ms p95={lat.total_ms_p95:.0f}ms"
    )
    print(
        f"  Split     : clean={lat.clean_turn_count} ({lat.clean_total_ms_p50:.0f}ms p50)  "
        f"flagged={lat.flagged_turn_count} ({lat.flagged_total_ms_p50:.0f}ms p50)"
    )
    print("=" * 62)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, results: list[ProductCaseResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(results[0].to_dict().keys()) if results else []
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_dict())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RAGE product benchmark — ChatGate + BotProfile (~20 cases)",
    )
    parser.add_argument(
        "--profile",
        default="practice",
        help="Default profile when case omits profile field",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Offline rule judge (CI default, no API keys)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live judge API (requires keys)",
    )
    parser.add_argument("--batch", action="store_true", help="Table output, no per-case pause")
    parser.add_argument("--output", default=None, help="Write JSON results to PATH")
    parser.add_argument("--csv", default=None, help="Write CSV results to PATH")
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip LLM ping on live start",
    )
    args = parser.parse_args()

    if args.offline and args.live:
        print("Use either --offline or --live, not both.", file=sys.stderr)
        return 1
    live = args.live or not args.offline

    if live:
        ok, err = ensure_llm_ready(
            interactive=sys.stdin.isatty(),
            verify=not args.no_verify,
            require_judge=True,
            force_prompt=sys.stdin.isatty(),
            dual_api=sys.stdin.isatty(),
        )
        if not ok:
            print(err, file=sys.stderr)
            return 1

    cases = load_product_holdout(default_profile=args.profile)
    scenarios = load_product_scenarios(default_profile=args.profile)
    mode = "live" if live else "offline"

    print()
    print("=" * 62)
    print(f"  RAGE Product Benchmark — {len(cases)} ST + {len(scenarios)} MT scenarios")
    print(f"  Mode: {mode.upper()}  |  default profile: {args.profile}")
    print("=" * 62)

    results = run_product_benchmark(
        cases,
        scenarios,
        use_judge_api=live,
    )

    if args.batch:
        _print_table(results)
    else:
        for result in results:
            label = "ATTACK" if result.is_attack else "BENIGN"
            print(f"\n[{result.case_id}] profile={result.profile_id} label={label}")
            print(f"  text    : {_truncate(result.text, 70)}")
            print(
                f"  verdict : {result.action.upper()}  outcome={result.outcome}  "
                f"override={'yes' if result.judge_override else 'no'}"
            )
            print(
                f"  latency : rage={result.rage_ms:.0f}ms judge={result.judge_ms:.0f}ms "
                f"total={result.total_ms:.0f}ms"
            )

    _print_summary(results)

    run_id = datetime.now(timezone.utc).isoformat()
    payload = export_run_json(
        results,
        mode=mode,
        profile_default=args.profile,
        run_id=run_id,
    )
    if args.output:
        out_path = Path(args.output)
        _write_json(out_path, payload)
        print(f"\nJSON → {out_path}")
    if args.csv:
        csv_path = Path(args.csv)
        _write_csv(csv_path, results)
        print(f"CSV  → {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
