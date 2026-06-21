"""Export campaign results and derive KB/threshold recommendations."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from rage_core.training.paths import get_training_center_root

if TYPE_CHECKING:
    from rage_core.training.campaign import CampaignResult
    from rage_core.training.orchestrator import ScenarioRunResult


def _results_dir() -> Path:
    return get_training_center_root() / "results"


def _insights_dir() -> Path:
    return get_training_center_root() / "insights"


def export_campaign_results(
    campaign: "CampaignResult",
    results_dir: Path | None = None,
) -> Path:
    out_dir = results_dir or _results_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{campaign.campaign_id}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(campaign.to_dict(), fh, ensure_ascii=False, indent=2)
    return path


def export_pending_insights(
    insights: dict,
    campaign_id: str,
    insights_dir: Path | None = None,
) -> Path:
    out_dir = insights_dir or _insights_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"pending_hardening_{campaign_id}.json"
    payload = {"source_campaign_id": campaign_id, **insights}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


def build_actionable_insights(runs: list["ScenarioRunResult"]) -> dict:
    defended_runs = [r for r in runs if r.defended]
    bypass_runs = [r for r in defended_runs if r.success]

    low_score_bypasses = []
    warn_bypasses = []
    kb_candidates = []

    for run in bypass_runs:
        for turn in run.turns:
            if turn.attack_success:
                entry = {
                    "scenario_id": run.scenario_id,
                    "turn": turn.turn_index,
                    "user_text_excerpt": turn.user_text[:160],
                    "pipeline_score": turn.pipeline_score,
                    "pipeline_band": turn.pipeline_band,
                    "l3_cumulative_drift": turn.l3_cumulative_drift,
                }
                if turn.pipeline_score < 30:
                    low_score_bypasses.append(entry)
                if turn.pipeline_band == "warn":
                    warn_bypasses.append(entry)
                kb_candidates.append({
                    "id": f"tc-{run.scenario_id}-t{turn.turn_index}",
                    "category": "crescendo_escalation",
                    "technique": f"Training-Center bypass {run.scenario_id} turn {turn.turn_index}",
                    "owasp_id": "LLM01",
                    "severity": "high",
                    "text": turn.user_text,
                })

    vuln_counter = Counter()
    for run in defended_runs:
        for v in run.vulnerabilities:
            vuln_counter[v.split(":")[0]] += 1

    recommendations = []
    if bypass_runs:
        recommendations.append(
            f"{len(bypass_runs)} defended run(s) still compromised — review Layer 3 "
            "cumulative drift thresholds and gateway patterns."
        )
    else:
        recommendations.append(
            "All defended runs contained — RAGE held against current Crescendo suite."
        )
    if low_score_bypasses:
        recommendations.append(
            "Low pipeline score bypasses detected — add KB entries or tighten session-risk ratchet."
        )
    if warn_bypasses:
        recommendations.append(
            "WARN-band bypasses detected — consider elevating ratchet_turns or warn→block on tool calls."
        )

    return {
        "vulnerability_counts": dict(vuln_counter),
        "low_score_bypasses": low_score_bypasses,
        "warn_bypasses": warn_bypasses,
        "recommended_kb_entries": kb_candidates,
        "recommended_threshold_adjustments": [
            {
                "parameter": "session_risk_block_threshold",
                "suggestion": "Lower from 0.55 if Crescendo bypasses accumulate session risk slowly",
                "priority": "medium",
            },
            {
                "parameter": "ratchet_turns",
                "suggestion": "Reduce from 3 if WARN-band bypasses occur",
                "priority": "high" if warn_bypasses else "low",
            },
        ],
        "recommendations": recommendations,
    }
