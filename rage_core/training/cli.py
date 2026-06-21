"""
CLI entry point for ``uv run rage-training``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rage_core.training.campaign import TrainingCampaign
from rage_core.training.paths import get_training_center_root
from rage_core.training.reporter import export_campaign_results, export_pending_insights
from rage_core.training.scenarios import load_all_scenarios


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RAGE Training-Center – Crescendo campaign")
    p.add_argument(
        "--scenarios",
        nargs="*",
        default=None,
        help="Scenario IDs (default: all built-in rage_core scenarios)",
    )
    p.add_argument("--iterations", type=int, default=1)
    p.add_argument("--no-baseline", action="store_true", help="Skip undefended baseline runs")
    p.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Override results directory (default: Training-Center/results/)",
    )
    return p.parse_args()


def print_summary(result) -> None:
    s = result.summary
    print("\n" + "═" * 72)
    print(f"{'TRAINING-CENTER – CRESCENDO × RAGE CAMPAIGN':^72}")
    print("═" * 72)
    print(f"  Campaign ID       : {result.campaign_id}")
    print(f"  Total runs        : {s.total_runs}")
    print(f"  Defended ASR      : {s.defended_asr:.1%}  ({s.defended_successes} successes)")
    print(f"  Baseline ASR      : {s.baseline_asr:.1%}  ({s.baseline_successes} successes)")
    if s.asr_reduction is not None:
        print(f"  RAGE ASR reduction: {s.asr_reduction:.1%}")
    print("\n  Per-scenario:")
    for _key, stats in sorted(s.scenario_breakdown.items()):
        print(
            f"    {stats['scenario_id']:28s} [{stats['mode']:22s}] "
            f"ASR={stats['asr']:.1%} ({stats['successes']}/{stats['runs']})"
        )
    print("═" * 72 + "\n")


def main() -> int:
    args = parse_args()
    results_dir = args.results_dir or (get_training_center_root() / "results")

    campaign = TrainingCampaign(
        iterations=args.iterations,
        include_baseline=not args.no_baseline,
        scenario_ids=args.scenarios,
    )
    packs = load_all_scenarios(args.scenarios)
    result = campaign.run(packs=packs)

    results_path = export_campaign_results(result, results_dir)
    insights_path = export_pending_insights(result.actionable_insights, result.campaign_id)

    print_summary(result)
    print(f"  📄 Results  : {results_path}")
    print(f"  📋 Insights : {insights_path}")
    print(
        f"\n  Apply: uv run rage-training-apply --campaign {result.campaign_id}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
