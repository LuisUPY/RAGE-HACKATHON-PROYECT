"""
CLI entry point: rage-demo

Runs all attack scenarios (with and without defense) and prints:
  - Per-turn defense decisions
  - Gateway verdicts
  - AUC report
  - Saves AUC plot to auc_results.png

Usage:
    uv run rage-demo
    uv run rage-demo --scenario drop_table_escalation
    uv run rage-demo --no-plot
"""
from __future__ import annotations

import argparse
import sys

from rage_core.demo.agent import SalesAgent
from rage_core.demo.attacks import ALL_SCENARIOS, Turn
from rage_core.layers.layer4_decision import DefensePipeline
from rage_core.metrics.auc_degradation import (
    AUCResult,
    compute_auc,
    plot_auc_curves,
    print_auc_report,
)
from rage_core.metrics.evaluator import score_conversation
from rage_core.models import Band, ConversationState


def run_scenario(
    scenario_name: str,
    turns: list[Turn],
    defended: bool,
) -> tuple[list[int], list]:
    """Run one scenario and return (gt_scores, gateway_verdicts)."""
    pipeline = DefensePipeline()
    state = ConversationState()
    agent = SalesAgent(defended=defended)

    label = "DEFENDED" if defended else "UNDEFENDED"
    print(f"\n{'='*64}")
    print(f"  Scenario: {scenario_name!r}  |  Mode: {label}")
    print(f"{'='*64}")

    turn_signals = []
    gateway_verdicts = []

    for i, turn in enumerate(turns):
        signal = pipeline.evaluate(turn.user_text, state)
        turn_signals.append(signal)

        print(f"\n  [T{i}] {turn.description}")
        print(f"        Text   : {turn.user_text[:80]!r}{'...' if len(turn.user_text) > 80 else ''}")
        print(f"        L1     : matched={signal.layer1.matched}  pattern={signal.layer1.pattern_id}")
        print(f"        L2     : score={signal.layer2.score:.3f}  cat={signal.layer2.top_match_category}")
        print(f"        L3     : drift={signal.layer3.drift:.3f}  suspicious={signal.layer3.suspicious}")
        print(f"        Score  : {signal.score:.1f}  Band: [{signal.band.value.upper()}]  latency={signal.latency_ms:.1f}ms")

        # Execute tool call if the pipeline allows it
        verdict = None
        if turn.tool_name and signal.band != Band.BLOCK:
            result = agent.call_tool(turn.tool_name, **(turn.tool_args or {}))
            if agent.verdicts:
                verdict = agent.verdicts[-1]
            status = "PERMITTED" if result.success else "BLOCKED"
            print(f"        Tool   : {turn.tool_name}({turn.tool_args}) → {status}")
            if not result.success:
                print(f"        Reason : {result.error}")
        elif turn.tool_name and signal.band == Band.BLOCK:
            print(f"        Tool   : {turn.tool_name} → SKIPPED (turn blocked by pipeline)")

        gateway_verdicts.append(verdict)

    # Ground-truth scoring
    gt_scores = score_conversation(turn_signals, gateway_verdicts)
    print(f"\n  Ground-truth scores: {gt_scores}")
    return gt_scores, gateway_verdicts


def main() -> None:
    parser = argparse.ArgumentParser(description="RAGE demo — multi-turn attack scenarios")
    parser.add_argument(
        "--scenario",
        choices=list(ALL_SCENARIOS.keys()) + ["all"],
        default="all",
        help="Which scenario to run (default: all)",
    )
    parser.add_argument("--no-plot", action="store_true", help="Skip matplotlib plot")
    args = parser.parse_args()

    scenario_names = (
        list(ALL_SCENARIOS.keys())
        if args.scenario == "all"
        else [args.scenario]
    )

    all_auc_results: list[AUCResult] = []

    for name in scenario_names:
        turns = ALL_SCENARIOS[name]
        # Run without defense (baseline)
        gt_undefended, _ = run_scenario(name, turns, defended=False)
        # Run with defense
        gt_defended, _ = run_scenario(name, turns, defended=True)

        auc_undefended = compute_auc(f"{name} — without defense", gt_undefended)
        auc_defended = compute_auc(f"{name} — with defense", gt_defended)
        all_auc_results.extend([auc_undefended, auc_defended])

    print_auc_report(all_auc_results)

    if not args.no_plot:
        try:
            plot_auc_curves(
                all_auc_results,
                output_path="auc_results.png",
                show=False,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] Could not save plot: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
