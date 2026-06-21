"""Batch campaign runner – defended vs baseline ASR aggregation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from rage_core.training.orchestrator import ScenarioOrchestrator, ScenarioRunResult
from rage_core.training.reporter import build_actionable_insights
from rage_core.training.scenarios import ScenarioPack, load_all_scenarios


@dataclass
class CampaignSummary:
    total_runs: int
    attack_successes: int
    attack_success_rate: float
    defended_successes: int
    defended_asr: float
    baseline_successes: int
    baseline_asr: float
    asr_reduction: float | None
    scenario_breakdown: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CampaignResult:
    campaign_id: str
    generated_at: str
    config: dict
    summary: CampaignSummary
    runs: list[ScenarioRunResult]
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


class TrainingCampaign:
    def __init__(
        self,
        iterations: int = 1,
        include_baseline: bool = True,
        scenario_ids: list[str] | None = None,
    ) -> None:
        self.iterations = iterations
        self.include_baseline = include_baseline
        self.scenario_ids = scenario_ids
        self._orchestrator = ScenarioOrchestrator()

    def run(self, packs: list[ScenarioPack] | None = None) -> CampaignResult:
        scenario_list = packs or load_all_scenarios(self.scenario_ids)
        if not scenario_list:
            raise ValueError("No scenarios to run")

        runs: list[ScenarioRunResult] = []
        for pack in scenario_list:
            for iteration in range(1, self.iterations + 1):
                runs.append(
                    self._orchestrator.run(
                        pack, defended=True, mode="with_rage", iteration=iteration
                    )
                )
                if self.include_baseline:
                    runs.append(
                        self._orchestrator.run(
                            pack,
                            defended=False,
                            mode="baseline_no_rage",
                            iteration=iteration,
                        )
                    )

        summary = self._summarize(runs)
        insights = build_actionable_insights(runs)
        campaign_id = datetime.now(timezone.utc).strftime("crescendo_%Y%m%d_%H%M%S")

        return CampaignResult(
            campaign_id=campaign_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            config={
                "iterations": self.iterations,
                "include_baseline": self.include_baseline,
                "scenario_ids": [p.id for p in scenario_list],
                "stack": "rage_core DefensePipeline + SalesAgent",
            },
            summary=summary,
            runs=runs,
            actionable_insights=insights,
        )

    def _summarize(self, runs: list[ScenarioRunResult]) -> CampaignSummary:
        defended = [r for r in runs if r.defended]
        baseline = [r for r in runs if not r.defended]

        def asr(subset: list[ScenarioRunResult]) -> float:
            if not subset:
                return 0.0
            return sum(1 for r in subset if r.success) / len(subset)

        defended_asr = asr(defended)
        baseline_asr = asr(baseline)

        breakdown: dict[str, dict] = {}
        for run in runs:
            key = f"{run.scenario_id}:{run.mode}"
            if key not in breakdown:
                breakdown[key] = {
                    "scenario_id": run.scenario_id,
                    "mode": run.mode,
                    "runs": 0,
                    "successes": 0,
                    "asr": 0.0,
                }
            breakdown[key]["runs"] += 1
            if run.success:
                breakdown[key]["successes"] += 1
            breakdown[key]["asr"] = breakdown[key]["successes"] / breakdown[key]["runs"]

        return CampaignSummary(
            total_runs=len(runs),
            attack_successes=sum(1 for r in runs if r.success),
            attack_success_rate=sum(1 for r in runs if r.success) / len(runs) if runs else 0.0,
            defended_successes=sum(1 for r in defended if r.success),
            defended_asr=defended_asr,
            baseline_successes=sum(1 for r in baseline if r.success),
            baseline_asr=baseline_asr,
            asr_reduction=(baseline_asr - defended_asr) if baseline else None,
            scenario_breakdown=breakdown,
        )
