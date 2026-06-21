"""
Adaptive Crescendo red-team loop.

Runs iterations of the Crescendo attack against the RAGE defense stack,
records bypasses in VulnerabilityDB, optionally auto-patches and retries.

Designed to run in a background thread controlled by threading.Event signals
published by the interactive menu (stop_event, pause_event) and a queue for
model swap requests.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rage_core.demo.agent import SalesAgent
from rage_core.layers.layer4_decision import DefensePipeline
from rage_core.models import ActionStatus, Band, ConversationState, GatewaySessionContext, GatewayVerdict, TurnSignal
from rage_core.redteam.attack_llm import CrescendoAttackLLM, GeneratedTurn
from rage_core.redteam.vulnerability_db import Vulnerability, VulnerabilityDB
from rage_core.training.paths import get_training_center_root

logger = logging.getLogger("redteam.loop")


@dataclass
class RedTeamConfig:
    iterations: int = 20
    unlimited: bool = False     # run until stop_event — ignores iterations
    severity: str = "medium"    # light / medium / high / critical
    max_turns: int = 12
    max_backtracks: int = 10
    objectives: list[str] = field(default_factory=lambda: ["exfil", "ddl"])
    model: str = "offline"
    auto_patch: bool = True
    scale: str = "medio"

    @staticmethod
    def from_scale(scale: str) -> "RedTeamConfig":
        presets = {
            "light": dict(iterations=5,  max_turns=8,  max_backtracks=5),
            "medio": dict(iterations=20, max_turns=12, max_backtracks=10),
            "heavy": dict(iterations=50, max_turns=20, max_backtracks=10),
        }
        kwargs = presets.get(scale, presets["medio"])
        return RedTeamConfig(scale=scale, **kwargs)


@dataclass
class TurnRecord:
    turn_index: int
    user_text: str
    is_attack: bool
    source: str
    pipeline_score: float
    pipeline_band: str
    l1_matched: bool
    l2_score: float
    l3_drift: float
    l3_cumulative_drift: float
    session_risk: float
    tool_permitted: bool | None
    gateway_reason: str | None
    attack_success: bool
    backtrack: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IterationResult:
    iteration: int
    objective: str
    model_used: str
    success: bool
    bypass_turn: int | None
    turns: list[TurnRecord] = field(default_factory=list)
    vulnerability_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["turns"] = [t.to_dict() for t in self.turns]
        return d


@dataclass
class IterationStatus:
    """Published to status_queue after each turn so the menu panel can refresh."""
    iteration: int
    total_iterations: int
    objective: str
    turn: int
    max_turns: int
    band: str
    score: float
    total_bypasses: int
    total_patched: int
    model: str
    unlimited: bool = False
    severity: str = "medium"
    paused: bool = False


@dataclass
class RedTeamCampaignResult:
    campaign_id: str
    generated_at: str
    config: dict[str, Any]
    iterations: list[IterationResult] = field(default_factory=list)
    total_bypasses: int = 0
    total_patched: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["iterations"] = [it.to_dict() for it in self.iterations]
        return d


class AdaptiveRedTeamLoop:
    """
    Orchestrates the full adaptive Crescendo campaign.

    Parameters
    ----------
    config:
        Campaign configuration (iterations, scale, objectives, model, …).
    stop_event:
        Set by the menu when the user presses S/Q. Loop exits cleanly after
        the current iteration completes.
    pause_event:
        Toggled by menu P key. Loop sleeps between iterations while set.
    model_queue:
        Queue of model name strings from the menu M key. Consumed at iteration
        boundaries.
    status_queue:
        Loop publishes IterationStatus objects here after every turn so the
        menu panel can refresh without blocking.
    vuln_db:
        Optional external VulnerabilityDB; a default one is created if None.
    patch_fn:
        Optional callable(Vulnerability) → bool that applies a patch and
        returns True if successful. Defaults to PatchGenerator.
    """

    def __init__(
        self,
        config: RedTeamConfig,
        stop_event: threading.Event | None = None,
        pause_event: threading.Event | None = None,
        model_queue: "queue.Queue[str] | None" = None,
        status_queue: "queue.Queue[IterationStatus] | None" = None,
        vuln_db: VulnerabilityDB | None = None,
        patch_fn: Any = None,
        unlimited_event: threading.Event | None = None,
    ) -> None:
        self.config = config
        self._stop = stop_event or threading.Event()
        self._pause = pause_event or threading.Event()
        self._model_q: "queue.Queue[str]" = model_queue or queue.Queue()
        self._status_q: "queue.Queue[IterationStatus]" = status_queue or queue.Queue()
        # External event to toggle unlimited mode from the live panel at runtime
        self._unlimited_ev = unlimited_event

        tc_root = get_training_center_root()
        self._vuln_db = vuln_db or VulnerabilityDB(tc_root / "vulnerabilities" / "vuln_db.json")

        self._attacker = CrescendoAttackLLM(model=config.model, severity=config.severity)
        self._patch_fn = patch_fn or self._default_patch

        self._campaign_id = datetime.now(timezone.utc).strftime("redteam_%Y%m%d_%H%M%S")
        self._results: list[IterationResult] = []
        self._total_bypasses = 0
        self._total_patched = 0

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    def _is_unlimited(self) -> bool:
        """True if unlimited mode is active (config flag or external event)."""
        return self.config.unlimited or (
            self._unlimited_ev is not None and self._unlimited_ev.is_set()
        )

    def run_campaign(self) -> RedTeamCampaignResult:
        unlimited = self._is_unlimited()
        logger.debug(
            "Red-team campaign %s starting (%s, severity=%s)",
            self._campaign_id,
            "∞ unlimited" if unlimited else f"{self.config.iterations} iterations",
            self.config.severity,
        )

        objectives = self.config.objectives
        i = 0

        while True:
            if self._stop.is_set():
                logger.debug("Stop signal — exiting after %d iterations", i)
                break

            # Check unlimited flag (can change at runtime via external event)
            if not self._is_unlimited() and i >= self.config.iterations:
                break

            # Respect pause between iterations
            while self._pause.is_set() and not self._stop.is_set():
                time.sleep(0.2)

            # Consume model swap request
            try:
                new_model = self._model_q.get_nowait()
                self._attacker.swap_model(new_model)
                logger.debug("Model swapped to %r for iteration %d", new_model, i + 1)
            except queue.Empty:
                pass

            objective = objectives[i % len(objectives)]
            result = self._run_iteration(i + 1, objective)
            self._results.append(result)

            if result.success:
                self._total_bypasses += 1
                vuln = self._vuln_db.pending_patches()[-1] if self._vuln_db.pending_patches() else None
                if self.config.auto_patch and vuln:
                    patched = self._patch_fn(vuln)
                    if patched:
                        self._vuln_db.mark_patched(vuln.id)
                        self._total_patched += 1

            i += 1

        campaign = RedTeamCampaignResult(
            campaign_id=self._campaign_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            config=asdict(self.config),
            iterations=self._results,
            total_bypasses=self._total_bypasses,
            total_patched=self._total_patched,
        )
        self._save_results(campaign)
        logger.debug(
            "Campaign %s complete — %d iterations, %d bypasses",
            self._campaign_id, i, self._total_bypasses,
        )
        return campaign

    # ------------------------------------------------------------------ #
    # Single iteration                                                     #
    # ------------------------------------------------------------------ #

    def _run_iteration(self, iteration: int, objective: str) -> IterationResult:
        pipeline = DefensePipeline()
        state = ConversationState()
        agent = SalesAgent(defended=True)
        history: list[dict] = []
        records: list[TurnRecord] = []

        success = False
        bypass_turn: int | None = None
        vuln_id: str | None = None
        last_signal: TurnSignal | None = None
        backtrack_count = 0

        logger.debug("Iteration %d/%d — objective=%s model=%s",
                    iteration, self.config.iterations, objective, self._attacker.current_model)

        for turn_idx in range(self.config.max_turns):
            if self._stop.is_set():
                break

            generated: GeneratedTurn = self._attacker.next_turn(
                history=history,
                objective=objective,
                turn_index=turn_idx,
                last_signal=last_signal,
            )
            turn = generated.to_turn()

            # -- Pipeline evaluation --
            last_signal = pipeline.evaluate(turn.user_text, state)
            band = last_signal.band

            # -- Publish status --
            self._publish_status(
                iteration=iteration,
                objective=objective,
                turn=turn_idx + 1,
                signal=last_signal,
            )

            tool_permitted: bool | None = None
            gateway_reason: str | None = None
            attack_success = False

            if band == Band.BLOCK:
                gateway_reason = "pipeline BLOCK"
                if backtrack_count < self.config.max_backtracks and generated.is_attack:
                    rephrased = self._attacker.rephrase(generated, "pipeline BLOCK", objective)
                    backtrack_count += 1
                    records.append(self._make_record(
                        turn_idx, generated, last_signal, state, None, None, False, backtrack=True
                    ))
                    last_signal = pipeline.evaluate(rephrased.user_text, state)
                    band = last_signal.band
                    generated = rephrased
                    turn = rephrased.to_turn()

            if band == Band.WARN and pipeline.warn_blocks_tools:
                if turn.tool_name:
                    tool_permitted = False
                    gateway_reason = "pipeline WARN — tools disabled"
            elif band == Band.ALLOW and turn.tool_name:
                session_ctx = GatewaySessionContext(
                    session_risk_score=state.session_risk_score,
                    had_warn_or_block=state.had_warn_or_block,
                )
                tool_result = agent.call_tool(
                    turn.tool_name,
                    session_context=session_ctx,
                    **(turn.tool_args or {}),
                )
                if agent.verdicts:
                    verdict = agent.verdicts[-1]
                    tool_permitted = verdict.status == ActionStatus.PERMITTED
                    gateway_reason = verdict.reason
                else:
                    tool_permitted = tool_result.success
                    gateway_reason = "no verdict"

                if tool_permitted and turn.is_attack:
                    attack_success = True
                    success = True
                    bypass_turn = turn_idx + 1

            if band != Band.BLOCK:
                history.append({"role": "user", "content": turn.user_text})
                history.append({"role": "assistant", "content": "[agent response]"})

            records.append(self._make_record(
                turn_idx, generated, last_signal, state, tool_permitted, gateway_reason, attack_success
            ))

            if attack_success:
                sql_used = turn.tool_args.get("sql", "") if turn.tool_args else ""
                vuln = Vulnerability(
                    id=Vulnerability.make_id(objective, turn.user_text),
                    objective=objective,
                    bypass_turn=bypass_turn or turn_idx + 1,
                    user_text=turn.user_text,
                    sql_executed=sql_used,
                    pipeline_score=last_signal.score,
                    pipeline_band=last_signal.band.value,
                    l1_matched=last_signal.layer1.matched,
                    l2_score=last_signal.layer2.score,
                    l3_drift=last_signal.layer3.drift,
                    l3_cumulative_drift=last_signal.layer3.cumulative_drift,
                    session_risk=state.session_risk_score,
                    model_used=self._attacker.current_model,
                    patch_applied=False,
                    discovered_at=datetime.now(timezone.utc).isoformat(),
                    campaign_id=self._campaign_id,
                )
                self._vuln_db.add(vuln)
                vuln_id = vuln.id
                logger.debug("BYPASS confirmed at turn %d — %s", bypass_turn, vuln_id)
                break

        return IterationResult(
            iteration=iteration,
            objective=objective,
            model_used=self._attacker.current_model,
            success=success,
            bypass_turn=bypass_turn,
            turns=records,
            vulnerability_id=vuln_id,
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _make_record(
        self,
        turn_idx: int,
        generated: GeneratedTurn,
        signal: TurnSignal,
        state: ConversationState,
        tool_permitted: bool | None,
        gateway_reason: str | None,
        attack_success: bool,
        backtrack: bool = False,
    ) -> TurnRecord:
        return TurnRecord(
            turn_index=turn_idx,
            user_text=generated.user_text,
            is_attack=generated.is_attack,
            source=generated.source,
            pipeline_score=signal.score,
            pipeline_band=signal.band.value,
            l1_matched=signal.layer1.matched,
            l2_score=signal.layer2.score,
            l3_drift=signal.layer3.drift,
            l3_cumulative_drift=signal.layer3.cumulative_drift,
            session_risk=round(state.session_risk_score, 4),
            tool_permitted=tool_permitted,
            gateway_reason=gateway_reason,
            attack_success=attack_success,
            backtrack=backtrack,
        )

    def _publish_status(
        self,
        iteration: int,
        objective: str,
        turn: int,
        signal: TurnSignal,
    ) -> None:
        try:
            self._status_q.put_nowait(IterationStatus(
                iteration=iteration,
                total_iterations=self.config.iterations,
                objective=objective,
                turn=turn,
                max_turns=self.config.max_turns,
                band=signal.band.value,
                score=signal.score,
                total_bypasses=self._total_bypasses,
                total_patched=self._total_patched,
                model=self._attacker.current_model,
                unlimited=self._is_unlimited(),
                severity=self.config.severity,
                paused=self._pause.is_set(),
            ))
        except queue.Full:
            pass

    def _default_patch(self, vuln: "Vulnerability") -> bool:
        """Lazy import to avoid circular dependency."""
        from rage_core.redteam.patch_generator import PatchGenerator
        pg = PatchGenerator()
        proposal = pg.from_vulnerability(vuln)
        return pg.apply(proposal)

    def _save_results(self, campaign: RedTeamCampaignResult) -> None:
        tc_root = get_training_center_root()
        out_dir = tc_root / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{campaign.campaign_id}.json"
        import json
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(campaign.to_dict(), fh, ensure_ascii=False, indent=2)
        logger.debug("Campaign results saved to %s", path)
