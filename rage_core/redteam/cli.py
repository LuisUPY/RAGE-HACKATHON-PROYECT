"""
Entry point: ``uv run rage-redteam``

Two launch modes:
  Interactive (default) — opens curses config menu, then live panel.
  Headless (--no-interactive) — all options via CLI flags, no curses.
"""

from __future__ import annotations

import argparse
import json
import logging
import queue
import sys
import threading
from pathlib import Path

from rage_core.redteam.loop import AdaptiveRedTeamLoop, RedTeamConfig
from rage_core.redteam.vulnerability_db import VulnerabilityDB
from rage_core.training.paths import get_training_center_root

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("redteam.cli")


# --------------------------------------------------------------------------- #
# CLI args                                                                    #
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="RAGE Adaptive Crescendo Red-Teamer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run rage-redteam                          # interactive menu
  uv run rage-redteam --no-interactive --scale light
  uv run rage-redteam --no-interactive --objectives exfil ddl --iterations 10
  uv run rage-redteam --no-interactive --model gpt-4o-mini --auto-patch --patch-and-retry
""",
    )
    p.add_argument("--no-interactive", action="store_true",
                   help="Skip curses menus, use CLI flags only")
    p.add_argument("--scale", choices=["light", "medio", "heavy"], default="medio",
                   help="Campaign scale shortcut (sets iterations + max_turns)")
    p.add_argument("--iterations", type=int, default=None,
                   help="Override total iterations (overrides --scale)")
    p.add_argument("--max-turns", type=int, default=None,
                   help="Override max turns per iteration")
    p.add_argument("--max-backtracks", type=int, default=10)
    p.add_argument("--objectives", nargs="+",
                   choices=["exfil", "ddl", "schema_dump", "canary", "privilege"],
                   default=["exfil", "ddl"],
                   help="Attack objectives to cycle through")
    p.add_argument("--model", choices=["offline", "gpt-4o-mini", "gpt-4o"],
                   default="offline")
    p.add_argument("--auto-patch", action="store_true", default=True,
                   help="Auto-apply patches after each bypass (default: on)")
    p.add_argument("--no-auto-patch", dest="auto_patch", action="store_false")
    p.add_argument("--patch-and-retry", action="store_true", default=True,
                   help="Re-run objective after patching to verify fix (default: on)")
    p.add_argument("--no-patch-and-retry", dest="patch_and_retry", action="store_false")
    p.add_argument("--results-dir", type=Path, default=None,
                   help="Override output directory for campaign JSON")
    return p.parse_args()


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #

def main() -> int:
    args = parse_args()

    # --- Build config --------------------------------------------------------
    if args.no_interactive:
        config = _config_from_args(args)
    else:
        config = _config_from_menu()
        if config is None:
            print("Aborted.")
            return 0

    _print_config_banner(config)

    # --- Shared signals ------------------------------------------------------
    stop_event: threading.Event = threading.Event()
    pause_event: threading.Event = threading.Event()
    model_queue: queue.Queue[str] = queue.Queue()
    status_queue: queue.Queue = queue.Queue(maxsize=64)

    tc_root = get_training_center_root()
    vuln_db = VulnerabilityDB(tc_root / "vulnerabilities" / "vuln_db.json")

    # --- Start loop in background thread ------------------------------------
    loop = AdaptiveRedTeamLoop(
        config=config,
        stop_event=stop_event,
        pause_event=pause_event,
        model_queue=model_queue,
        status_queue=status_queue,
        vuln_db=vuln_db,
    )

    result_holder: list = []

    def _run_loop() -> None:
        result = loop.run_campaign()
        result_holder.append(result)
        stop_event.set()

    loop_thread = threading.Thread(target=_run_loop, daemon=True)
    loop_thread.start()

    # --- Live panel (main thread) -------------------------------------------
    if args.no_interactive:
        _plain_monitor(stop_event, status_queue)
    else:
        from rage_core.redteam.menu import LivePanel
        panel = LivePanel(
            config=config,
            stop_event=stop_event,
            pause_event=pause_event,
            model_queue=model_queue,
            status_queue=status_queue,
            vuln_db=vuln_db,
        )
        panel.run()

    loop_thread.join(timeout=5)

    # --- Summary ------------------------------------------------------------
    if result_holder:
        _print_summary(result_holder[0], vuln_db)
    else:
        print("\n  Campaign stopped early — partial results saved.\n")

    return 0


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _config_from_args(args: argparse.Namespace) -> RedTeamConfig:
    base = RedTeamConfig.from_scale(args.scale)
    if args.iterations is not None:
        base.iterations = args.iterations
    if args.max_turns is not None:
        base.max_turns = args.max_turns
    base.max_backtracks = args.max_backtracks
    base.objectives = args.objectives
    base.model = args.model
    base.auto_patch = args.auto_patch
    base.patch_and_retry = args.patch_and_retry
    return base


def _config_from_menu() -> "RedTeamConfig | None":
    from rage_core.redteam.menu import ConfigMenu
    return ConfigMenu().run()


def _print_config_banner(config: RedTeamConfig) -> None:
    print("\n" + "═" * 60)
    print(f"{'  RAGE Adaptive Crescendo Red-Teamer':^60}")
    print("═" * 60)
    print(f"  Scale       : {config.scale}")
    print(f"  Iterations  : {config.iterations}")
    print(f"  Max turns   : {config.max_turns}")
    print(f"  Backtracks  : {config.max_backtracks}")
    print(f"  Objectives  : {', '.join(config.objectives)}")
    print(f"  Model       : {config.model}")
    print(f"  Auto-patch  : {'yes' if config.auto_patch else 'no'}")
    print(f"  Patch-retry : {'yes' if config.patch_and_retry else 'no'}")
    print("─" * 60)
    print("  [Ctrl+C] to stop at any time\n")


def _plain_monitor(
    stop_event: threading.Event,
    status_queue: "queue.Queue",
) -> None:
    import time
    try:
        while not stop_event.is_set():
            try:
                s = status_queue.get(timeout=0.5)
                print(
                    f"\r  iter {s.iteration}/{s.total_iterations} | "
                    f"obj={s.objective:<12s} | turn={s.turn}/{s.max_turns} | "
                    f"band={s.band:<5s} score={s.score:5.1f} | "
                    f"bypasses={s.total_bypasses} patched={s.total_patched}",
                    end="",
                    flush=True,
                )
            except Exception:
                pass
    except KeyboardInterrupt:
        stop_event.set()
    print()


def _print_summary(result: "RedTeamCampaignResult", vuln_db: VulnerabilityDB) -> None:
    print("\n" + "═" * 60)
    print(f"{'  CAMPAIGN COMPLETE':^60}")
    print("═" * 60)
    print(f"  Campaign ID   : {result.campaign_id}")
    print(f"  Iterations run: {len(result.iterations)}")
    print(f"  Bypasses found: {result.total_bypasses}")
    print(f"  Patches applied:{result.total_patched}")

    summary = vuln_db.summary()
    print(f"\n  Vulnerability DB: {summary['total']} total "
          f"({summary['patched']} patched, {summary['pending']} pending)")
    print(f"  By objective: {summary['by_objective']}")

    tc_root = get_training_center_root()
    print(f"\n  Results : {tc_root}/results/{result.campaign_id}.json")
    print(f"  VulnDB  : {tc_root}/vulnerabilities/vuln_db.json")
    print("═" * 60 + "\n")
    print("  Next step: uv run rage-training-apply --apply-kb\n")


if __name__ == "__main__":
    raise SystemExit(main())
