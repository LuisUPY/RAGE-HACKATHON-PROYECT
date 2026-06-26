"""Run locked eval set and compare or update regression baseline.

    uv run python scripts/update_benchmark_baseline.py --eval-set locked_v1 --combined --fast
    uv run python scripts/update_benchmark_baseline.py --eval-set locked_v1 --combined --fast --write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rage_core.benchmark.dataset import load_eval_holdout_dataset, load_eval_scenarios
from rage_core.benchmark.evaluator import compute_metrics, run_benchmark, run_multi_turn_benchmark

DEFAULT_BASELINE = ROOT / "benchmarks" / "baseline_locked_v1.json"


def _run_locked(*, eval_set: str, combined: bool, use_judge: bool) -> dict:
    if not combined:
        cases = load_eval_holdout_dataset(eval_set)
        results = run_benchmark(cases, use_judge=use_judge, multi_turn=False)
    else:
        st = run_benchmark(
            load_eval_holdout_dataset(eval_set),
            use_judge=use_judge,
            multi_turn=False,
        )
        mt = run_multi_turn_benchmark(
            load_eval_scenarios(eval_set),
            use_judge=use_judge,
        )
        results = st + mt
    m = compute_metrics(results)
    return {
        "recall": round(m.recall, 6),
        "precision": round(m.precision, 6),
        "accuracy": round(m.accuracy, 6),
        "fp": m.fp,
        "fn": m.fn,
        "tp": m.tp,
        "tn": m.tn,
        "total": m.total,
    }


def _manifest_sha(eval_set: str) -> str:
    manifest_path = ROOT / "rage_core" / "kb" / f"eval_{eval_set}" / "MANIFEST.json"
    if eval_set == "locked_v1":
        manifest_path = ROOT / "rage_core" / "kb" / "eval_locked_v1" / "MANIFEST.json"
    if not manifest_path.is_file():
        return ""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = data.get("files", {})
    holdout = files.get("holdout.json", {}).get("sha256", "")
    scenarios = files.get("scenarios.json", {}).get("sha256", "")
    return f"{holdout}:{scenarios}"


def _compare(current: dict, baseline: dict) -> list[str]:
    errors: list[str] = []
    tol = baseline.get("tolerance", {})
    fp_max = int(tol.get("fp_max", 0))
    recall_abs = float(tol.get("recall_abs", 0.02))

    bm = baseline["metrics"]
    if current["fp"] > fp_max:
        errors.append(f"FP {current['fp']} > max {fp_max}")
    if abs(current["recall"] - bm["recall"]) > recall_abs:
        errors.append(
            f"recall {current['recall']:.1%} differs from baseline {bm['recall']:.1%} "
            f"(tolerance ±{recall_abs:.1%})"
        )
    for key in ("tp", "fn", "tn", "total"):
        if current[key] != bm[key]:
            errors.append(f"{key} {current[key]} != baseline {bm[key]}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark baseline for frozen eval sets")
    parser.add_argument("--eval-set", default="locked_v1")
    parser.add_argument("--combined", action="store_true", default=True)
    parser.add_argument("--fast", action="store_true", help="L1+L2 only (no judge)")
    parser.add_argument("--write", action="store_true", help="Write baseline JSON")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    args = parser.parse_args()

    use_judge = not args.fast
    metrics = _run_locked(
        eval_set=args.eval_set,
        combined=args.combined,
        use_judge=use_judge,
    )

    print(f"eval_set={args.eval_set} mode={'L1+L2' if args.fast else 'L1+L2+Judge'}")
    print(
        f"recall={metrics['recall']:.1%} precision={metrics['precision']:.1%} "
        f"fp={metrics['fp']} fn={metrics['fn']} tp={metrics['tp']} total={metrics['total']}"
    )

    if args.write:
        payload = {
            "eval_set": args.eval_set,
            "mode": "L1+L2" if args.fast else "L1+L2+Judge",
            "use_judge": use_judge,
            "combined": args.combined,
            "metrics": metrics,
            "tolerance": {"recall_abs": 0.02, "fp_max": 0},
            "frozen_from_manifest_sha256": _manifest_sha(args.eval_set),
        }
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.baseline}")
        return 0

    if not args.baseline.is_file():
        print(f"ERROR: baseline missing: {args.baseline} (run with --write)", file=sys.stderr)
        return 1

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    errors = _compare(metrics, baseline)
    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("OK: within baseline tolerance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
