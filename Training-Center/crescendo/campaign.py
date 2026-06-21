"""
Campaign runner: batch Crescendo × RAGE experiments with ASR aggregation.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from decision_engine import PrincipalAgent  # noqa: E402

from .attack_generator import AttackGenerator
from .simulated_agent import SimulatedCrescendoAgent
from .gateway_factory import PassthroughGateway, build_rage_gateway
from .judge import CrescendoJudge
from .orchestrator import CrescendoOrchestrator, CrescendoRunResult
from .reporter import build_actionable_insights
from .scenarios import CrescendoScenario, load_scenarios

logger = logging.getLogger("training_center.campaign")


@dataclass
class CampaignSummary:
    total_runs: int
    successful_attacks: int
    attack_success_rate: float
    gateway_block_events: int
    gateway_bypass_count: int
    gateway_bypass_rate: float
    avg_turns_to_success: Optional[float]
    scenario_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CampaignResult:
    campaign_id: str
    generated_at: str
    config: dict
    summary: CampaignSummary
    runs: List[CrescendoRunResult]
    actionable_insights: dict

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "generated_at": self.generated_at,
            "config": self.config,
            "summary": self.summary.to_dict(),
            "runs": [r.to_dict() for r in self.runs],
            "actionable_insights": self.actionable_insights,
        }


class CrescendoCampaign:
    """Execute multiple Crescendo scenarios against RAGE with optional baseline."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        use_real_llm: bool = False,
        generator_mode: str = "scripted",
        use_llm_judge: bool = False,
        max_rounds: int = 10,
        max_backtracks: int = 10,
        iterations: int = 1,
        include_baseline: bool = True,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.use_real_llm = use_real_llm and bool(self.api_key)
        self.generator_mode = generator_mode
        self.use_llm_judge = use_llm_judge and bool(self.api_key)
        self.max_rounds = max_rounds
        self.max_backtracks = max_backtracks
        self.iterations = iterations
        self.include_baseline = include_baseline

    def run(
        self,
        scenarios: Optional[List[CrescendoScenario]] = None,
        scenario_ids: Optional[List[str]] = None,
    ) -> CampaignResult:
        scenario_list = scenarios or load_scenarios(scenario_ids=scenario_ids)
        if not scenario_list:
            raise ValueError("No scenarios loaded for campaign")

        runs: List[CrescendoRunResult] = []
        if self.use_real_llm:
            agent: Any = PrincipalAgent(use_real_llm=True, api_key=self.api_key)
        else:
            agent = SimulatedCrescendoAgent()
        judge = CrescendoJudge(use_llm_judge=self.use_llm_judge, api_key=self.api_key)
        generator = AttackGenerator(mode=self.generator_mode, api_key=self.api_key)

        modes: List[tuple[str, Any]] = [("with_gateway", build_rage_gateway(self.api_key))]
        if self.include_baseline:
            modes.append(("baseline_no_gateway", PassthroughGateway()))

        for scenario in scenario_list:
            for mode_name, gateway in modes:
                orchestrator = CrescendoOrchestrator(
                    gateway=gateway,
                    agent=agent,
                    judge=judge,
                    attack_generator=generator,
                    max_rounds=self.max_rounds,
                    max_backtracks=self.max_backtracks,
                )
                for iteration in range(1, self.iterations + 1):
                    logger.info(
                        "Running %s / %s / iter %d",
                        scenario.id,
                        mode_name,
                        iteration,
                    )
                    result = orchestrator.run(
                        scenario=scenario,
                        mode=mode_name,
                        iteration=iteration,
                    )
                    runs.append(result)

        summary = self._summarize(runs)
        insights = build_actionable_insights(runs, scenario_list)
        campaign_id = datetime.now(timezone.utc).strftime("crescendo_%Y%m%d_%H%M%S")

        return CampaignResult(
            campaign_id=campaign_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            config={
                "use_real_llm": self.use_real_llm,
                "generator_mode": self.generator_mode,
                "use_llm_judge": self.use_llm_judge,
                "max_rounds": self.max_rounds,
                "max_backtracks": self.max_backtracks,
                "iterations": self.iterations,
                "include_baseline": self.include_baseline,
                "scenario_ids": [s.id for s in scenario_list],
            },
            summary=summary,
            runs=runs,
            actionable_insights=insights,
        )

    def _summarize(self, runs: List[CrescendoRunResult]) -> CampaignSummary:
        total = len(runs)
        successes = sum(1 for r in runs if r.success)
        bypasses = sum(1 for r in runs if r.gateway_bypassed)
        blocks = sum(1 for r in runs if r.gateway_blocked)
        success_turns = [r.success_turn for r in runs if r.success and r.success_turn]

        scenario_breakdown: Dict[str, Dict[str, Any]] = {}
        for run in runs:
            key = f"{run.scenario_id}:{run.mode}"
            if key not in scenario_breakdown:
                scenario_breakdown[key] = {
                    "scenario_id": run.scenario_id,
                    "mode": run.mode,
                    "runs": 0,
                    "successes": 0,
                    "asr": 0.0,
                }
            scenario_breakdown[key]["runs"] += 1
            if run.success:
                scenario_breakdown[key]["successes"] += 1

        for stats in scenario_breakdown.values():
            stats["asr"] = (
                stats["successes"] / stats["runs"] if stats["runs"] else 0.0
            )

        return CampaignSummary(
            total_runs=total,
            successful_attacks=successes,
            attack_success_rate=successes / total if total else 0.0,
            gateway_block_events=blocks,
            gateway_bypass_count=bypasses,
            gateway_bypass_rate=bypasses / total if total else 0.0,
            avg_turns_to_success=(
                sum(success_turns) / len(success_turns) if success_turns else None
            ),
            scenario_breakdown=scenario_breakdown,
        )
