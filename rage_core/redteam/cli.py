"""
Entry point: ``uv run rage-redteam``  — v3

Two launch modes:
  Interactive (default) — opens curses config menu, then live panel.
    [U] in the live panel toggles unlimited mode on/off at runtime.
  Headless (--no-interactive) — all options via CLI flags, no curses.

Severity levels control attack aggressiveness (offline template selection):
  light    — benign turns only, no actual attacks
  medium   — sequential escalation (default)
  high     — attack turns start 2 steps earlier
  critical — jump straight to attack templates, cycle indefinitely
"""

from __future__ import annotations

import argparse
import logging
import queue
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from rage_core.redteam.loop import AdaptiveRedTeamLoop, RedTeamConfig
from rage_core.redteam.vulnerability_db import VulnerabilityDB
from rage_core.training.paths import get_training_center_root

if TYPE_CHECKING:
    from rage_core.redteam.loop import RedTeamCampaignResult

logger = logging.getLogger("redteam.cli")


def _setup_logging(interactive: bool, log_dir: Path) -> None:
    """Headless → stderr. Interactive → file (curses owns the terminal)."""
    if interactive:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.FileHandler(
            log_dir / "redteam.log", encoding="utf-8"
        )
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


# --------------------------------------------------------------------------- #
# CLI args                                                                    #
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="RAGE Adaptive Crescendo Red-Teamer — v3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run rage-redteam                              # interactive menu
  uv run rage-redteam --no-interactive --unlimited # run forever until Ctrl+C
  uv run rage-redteam --no-interactive --scale light --severity high
  uv run rage-redteam --no-interactive --objectives exfil ddl --iterations 10
  uv run rage-redteam --no-interactive --severity critical --unlimited
""",
    )
    p.add_argument("--no-interactive", action="store_true",
                   help="Skip curses menus, use CLI flags only")
    p.add_argument("--scale", choices=["light", "medio", "heavy"], default="medio",
                   help="Campaign scale shortcut (sets iterations + max_turns)")
    p.add_argument("--iterations", type=int, default=None,
                   help="Override total iterations (ignored when --unlimited is set)")
    p.add_argument("--unlimited", action="store_true", default=False,
                   help="Run indefinitely until stopped with Ctrl+C / [S] / [Q]")
    p.add_argument("--severity",
                   choices=["light", "medium", "high", "critical"],
                   default="medium",
                   help="Attack aggressiveness: light/medium/high/critical (default: medium)")
    p.add_argument("--max-turns", type=int, default=None,
                   help="Override max turns per iteration")
    p.add_argument("--max-backtracks", type=int, default=None,
                   help="Override max backtracks (default depends on scale)")
    p.add_argument("--objectives", nargs="+",
                   choices=["exfil", "ddl", "schema_dump", "canary", "privilege"],
                   default=["exfil", "ddl"],
                   help="Attack objectives to cycle through")
    p.add_argument("--model", choices=["offline", "gpt-4o-mini", "gpt-4o"],
                   default="offline")
    p.add_argument("--auto-patch", action="store_true", default=True,
                   help="Auto-apply patches after each bypass (default: on)")
    p.add_argument("--no-auto-patch", dest="auto_patch", action="store_false")
    p.add_argument("--results-dir", type=Path, default=None,
                   help="Override output directory for campaign JSON")
    return p.parse_args()


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #

def main() -> int:
    args = parse_args()
    tc_root = get_training_center_root()

    _setup_logging(
        interactive=not args.no_interactive,
        log_dir=tc_root / "logs",
    )

    if args.no_interactive:
        config = _config_from_args(args)
    else:
        config = _config_from_menu()
        if config is None:
            print("Aborted.")
            return 0

    _prewarm_pipeline()

    if args.no_interactive:
        _print_config_banner(config)

    # Shared signals
    stop_event: threading.Event = threading.Event()
    pause_event: threading.Event = threading.Event()
    model_queue: queue.Queue[str] = queue.Queue()
    status_queue: queue.Queue = queue.Queue(maxsize=128)
    # v3: unlimited_event allows LivePanel [U] to toggle mode at runtime
    unlimited_event: threading.Event = threading.Event()
    if config.unlimited:
        unlimited_event.set()

    vuln_db = VulnerabilityDB(tc_root / "vulnerabilities" / "vuln_db.json")

    loop = AdaptiveRedTeamLoop(
        config=config,
        stop_event=stop_event,
        pause_event=pause_event,
        model_queue=model_queue,
        status_queue=status_queue,
        vuln_db=vuln_db,
        unlimited_event=unlimited_event,
    )

    result_holder: list[RedTeamCampaignResult] = []

    def _run_loop() -> None:
        result = loop.run_campaign()
        result_holder.append(result)
        stop_event.set()

    loop_thread = threading.Thread(target=_run_loop, daemon=True, name="redteam-loop")
    loop_thread.start()

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
            unlimited_event=unlimited_event,
        )
        panel.run()

    loop_thread.join(timeout=10)

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
    if args.max_backtracks is not None:
        base.max_backtracks = args.max_backtracks
    base.objectives = args.objectives
    base.model = args.model
    base.auto_patch = args.auto_patch
    base.unlimited = args.unlimited
    base.severity = args.severity
    return base


def _prewarm_pipeline() -> None:
    """Load sklearn/TF-IDF in the main thread before curses/threads start."""
    try:
        from rage_core.layers.layer4_decision import DefensePipeline
        from rage_core.models import ConversationState
        DefensePipeline().evaluate("warm-up", ConversationState())
        logger.info("Pipeline pre-warmed successfully")
    except Exception as exc:
        logger.warning("Pipeline pre-warm failed (non-critical): %s", exc)


def _config_from_menu() -> "RedTeamConfig | None":
    from rage_core.redteam.menu import ConfigMenu
    return ConfigMenu().run()


def _print_config_banner(config: RedTeamConfig) -> None:
    print("\n" + "═" * 60)
    print(f"{'  RAGE Adaptive Crescendo Red-Teamer  v3':^60}")
    print("═" * 60)
    print(f"  Scale       : {config.scale}")
    iter_str = "∞ ilimitado" if config.unlimited else str(config.iterations)
    print(f"  Iterations  : {iter_str}")
    print(f"  Max turns   : {config.max_turns}")
    print(f"  Backtracks  : {config.max_backtracks}")
    print(f"  Objectives  : {', '.join(config.objectives)}")
    print(f"  Severity    : {config.severity}")
    print(f"  Model       : {config.model}")
    print(f"  Auto-patch  : {'yes' if config.auto_patch else 'no'}")
    print("─" * 60)
    print("  [Ctrl+C] to stop at any time\n")


def _plain_monitor(
    stop_event: threading.Event,
    status_queue: queue.Queue,
) -> None:
    try:
        while not stop_event.is_set():
            try:
                s = status_queue.get(timeout=0.5)
                iter_str = (f"∞({s.iteration})" if s.unlimited
                            else f"{s.iteration}/{s.total_iterations}")
                print(
                    f"\r  iter {iter_str:<8s} | obj={s.objective:<12s}"
                    f" | turn={s.turn}/{s.max_turns}"
                    f" | band={s.band:<5s} score={s.score:5.1f}"
                    f" | sev={s.severity}"
                    f" | bypasses={s.total_bypasses} patched={s.total_patched}",
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
    print(f"{'                CAMPAIGN COMPLETE':^60}")
    print("═" * 60)
    print(f"  Campaign ID   : {result.campaign_id}")
    print(f"  Iterations run: {len(result.iterations)}")
    print(f"  Bypasses found: {result.total_bypasses}")
    print(f"  Patches applied: {result.total_patched}")

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
