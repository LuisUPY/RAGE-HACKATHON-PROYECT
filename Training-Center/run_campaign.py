#!/usr/bin/env python3
"""
RAGE Training-Center – Crescendo campaign runner.

Automates multi-turn Crescendo red-teaming against the RAGE DecisionGateway,
exports results and actionable hardening insights.

Usage:
    python Training-Center/run_campaign.py
    python Training-Center/run_campaign.py --scenarios text2sql_exfil --iterations 3
    python Training-Center/run_campaign.py --real-llm --adaptive --llm-judge
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from crescendo.campaign import CrescendoCampaign  # noqa: E402
from crescendo.reporter import (  # noqa: E402
    export_actionable_insights,
    export_campaign_results,
)
from crescendo.scenarios import load_scenarios  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Crescendo × RAGE red-team campaign (Training-Center)"
    )
    parser.add_argument(
        "--scenarios",
        nargs="*",
        default=None,
        help="Scenario IDs to run (default: all in Training-Center/scenarios/)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Independent iterations per scenario/mode (paper default: 10)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=10,
        help="Max Crescendo interaction rounds per run",
    )
    parser.add_argument(
        "--max-backtracks",
        type=int,
        default=10,
        help="Max refusal backtracks per run",
    )
    parser.add_argument(
        "--real-llm",
        action="store_true",
        help="Use live OpenAI target agent (requires OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="Use LLM attack generator (Crescendomation-style) beyond scripted turns",
    )
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Enable LLM judge for success evaluation",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Skip baseline runs without RAGE gateway",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
        help="Directory for campaign JSON output",
    )
    return parser.parse_args()


def print_summary(campaign_result) -> None:
    s = campaign_result.summary
    print("\n" + "═" * 72)
    print(f"{'TRAINING-CENTER – CRESCENDO CAMPAIGN SUMMARY':^72}")
    print("═" * 72)
    print(f"  Campaign ID          : {campaign_result.campaign_id}")
    print(f"  Total runs           : {s.total_runs}")
    print(f"  Attack success rate  : {s.attack_success_rate:.1%}")
    print(f"  Gateway bypass rate  : {s.gateway_bypass_rate:.1%}")
    print(f"  Gateway block events : {s.gateway_block_events}")
    if s.avg_turns_to_success is not None:
        print(f"  Avg turns to success : {s.avg_turns_to_success:.1f}")
    print("\n  Per-scenario ASR:")
    for key, stats in sorted(s.scenario_breakdown.items()):
        print(
            f"    {stats['scenario_id']:30s} [{stats['mode']:20s}] "
            f"ASR={stats['asr']:.1%} ({stats['successes']}/{stats['runs']})"
        )
    metrics = campaign_result.actionable_insights.get("metrics", {})
    if metrics.get("asr_reduction") is not None:
        print(
            f"\n  RAGE ASR reduction   : {metrics['asr_reduction']:.1%} "
            f"(baseline {metrics['baseline_asr']:.1%} → gateway {metrics['gateway_asr']:.1%})"
        )
    print("═" * 72 + "\n")


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("OPENAI_API_KEY")

    if args.real_llm and not api_key:
        print("ERROR: --real-llm requires OPENAI_API_KEY")
        return 1

    mode_label = (
        "hybrid (live LLM)" if args.real_llm
        else "offline (simulated vulnerable agent)"
    )
    print(f"\n  RAGE Training-Center | Crescendo Campaign")
    print(f"  Mode: {mode_label}")
    print(f"  Generator: {'adaptive' if args.adaptive else 'scripted'}")
    print()

    campaign = CrescendoCampaign(
        api_key=api_key,
        use_real_llm=args.real_llm,
        generator_mode="adaptive" if args.adaptive else "scripted",
        use_llm_judge=args.llm_judge,
        max_rounds=args.max_rounds,
        max_backtracks=args.max_backtracks,
        iterations=args.iterations,
        include_baseline=not args.no_baseline,
    )

    scenarios = load_scenarios(scenario_ids=args.scenarios)
    result = campaign.run(scenarios=scenarios)

    results_path = export_campaign_results(result, args.results_dir)
    insights_path = export_actionable_insights(
        result.actionable_insights,
        result.campaign_id,
    )

    print_summary(result)
    print(f"  📄 Campaign results : {results_path}")
    print(f"  📋 Hardening insights: {insights_path}")
    print("\n  Apply insights later with:")
    print(f"    python Training-Center/apply_insights.py --campaign {result.campaign_id}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
