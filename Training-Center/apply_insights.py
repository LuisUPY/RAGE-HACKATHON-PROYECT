#!/usr/bin/env python3
"""
Apply Training-Center campaign insights to RAGE hardening artifacts.

Reads campaign results and pending hardening JSON, then generates:
  - insights/applied/threat_patterns.json  (KB candidates for InputFilter/RAG)
  - insights/applied/hardening_report.md   (human-readable summary)

Usage:
    python Training-Center/apply_insights.py
    python Training-Center/apply_insights.py --campaign crescendo_20250621_120000
    python Training-Center/apply_insights.py --dry-run
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

TRAINING_CENTER = Path(__file__).resolve().parent
RESULTS_DIR = TRAINING_CENTER / "results"
INSIGHTS_DIR = TRAINING_CENTER / "insights"
APPLIED_DIR = INSIGHTS_DIR / "applied"


def latest_campaign_id(results_dir: Path) -> Optional[str]:
    files = sorted(results_dir.glob("crescendo_*.json"), reverse=True)
    if not files:
        return None
    return files[0].stem


def load_campaign(campaign_id: str, results_dir: Path) -> dict:
    path = results_dir / f"{campaign_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Campaign not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_pending_insights(campaign_id: str) -> Optional[dict]:
    path = INSIGHTS_DIR / f"pending_hardening_{campaign_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_threat_patterns(campaign: dict, pending: Optional[dict]) -> List[dict]:
    patterns: List[dict] = []
    seen: set[str] = set()

    if pending:
        for regex in pending.get("recommended_kb_patterns", []):
            if regex not in seen:
                seen.add(regex)
                patterns.append({
                    "pattern": regex,
                    "score": 2,
                    "tag": "TC-Crescendo",
                    "description": "Crescendo escalation pattern from Training-Center",
                    "source_campaign": campaign.get("campaign_id"),
                })

    for run in campaign.get("runs", []):
        if run.get("mode") != "with_gateway" or not run.get("gateway_bypassed"):
            continue
        for turn in run.get("turns", []):
            if turn.get("gateway_score", 5) <= 2:
                excerpt = turn.get("prompt_excerpt") or turn.get("prompt", "")[:120]
                key = excerpt[:80]
                if key and key not in seen:
                    seen.add(key)
                    patterns.append({
                        "pattern": None,
                        "example_prompt": excerpt,
                        "score": 3,
                        "tag": "TC-Bypass",
                        "description": (
                            f"Low-score bypass turn {turn.get('turn')} "
                            f"scenario={run.get('scenario_id')}"
                        ),
                        "source_campaign": campaign.get("campaign_id"),
                    })

    return patterns


def build_markdown_report(
    campaign: dict,
    pending: Optional[dict],
    patterns: List[dict],
) -> str:
    summary = campaign.get("summary", {})
    metrics = (pending or {}).get("metrics", {})
    lines = [
        "# RAGE Training-Center – Hardening Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Source campaign: `{campaign.get('campaign_id')}`",
        "",
        "## Metrics",
        "",
        f"- **Attack success rate (all runs):** {summary.get('attack_success_rate', 0):.1%}",
        f"- **Gateway bypass rate:** {summary.get('gateway_bypass_rate', 0):.1%}",
    ]
    if metrics.get("baseline_asr") is not None:
        lines.extend([
            f"- **Baseline ASR (no gateway):** {metrics['baseline_asr']:.1%}",
            f"- **Gateway ASR:** {metrics['gateway_asr']:.1%}",
            f"- **ASR reduction:** {metrics.get('asr_reduction', 0):.1%}",
        ])
    lines.extend(["", "## Recommendations", ""])
    for rec in (pending or {}).get("recommendations", []):
        lines.append(f"- {rec}")
    if not (pending or {}).get("recommendations"):
        lines.append("- No critical recommendations (gateway contained attacks).")

    lines.extend(["", "## Suggested KB / InputFilter patterns", ""])
    for p in patterns:
        if p.get("pattern"):
            lines.append(f"- `[{p['tag']}]` `{p['pattern']}` (score +{p['score']})")
        else:
            lines.append(f"- `[{p['tag']}]` example: _{p.get('example_prompt', '')[:100]}_")

    lines.extend([
        "",
        "## Next steps",
        "",
        "1. Review patterns in `insights/applied/threat_patterns.json`.",
        "2. Add selected regex entries to `InputFilter.THREAT_PATTERNS` in `decision_engine.py`.",
        "3. Re-run `python Training-Center/run_campaign.py` and compare ASR.",
        "",
    ])
    return "\n".join(lines)


def apply_insights(
    campaign_id: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    campaign = load_campaign(campaign_id, RESULTS_DIR)
    pending = load_pending_insights(campaign_id)
    patterns = build_threat_patterns(campaign, pending)
    report = build_markdown_report(campaign, pending, patterns)

    output = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "source_campaign_id": campaign_id,
        "threat_pattern_count": len(patterns),
        "threat_patterns": patterns,
    }

    if dry_run:
        print(report)
        print(f"\n[DRY RUN] Would write {len(patterns)} patterns to {APPLIED_DIR}")
        return output

    APPLIED_DIR.mkdir(parents=True, exist_ok=True)
    patterns_path = APPLIED_DIR / f"threat_patterns_{campaign_id}.json"
    report_path = APPLIED_DIR / f"hardening_report_{campaign_id}.md"
    latest_path = APPLIED_DIR / "threat_patterns_latest.json"

    with open(patterns_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report)
    with open(latest_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)

    print(report)
    print(f"\n  ✅ Patterns → {patterns_path}")
    print(f"  ✅ Report   → {report_path}")
    print(f"  ✅ Latest   → {latest_path}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Training-Center insights to RAGE")
    parser.add_argument("--campaign", default=None, help="Campaign ID (default: latest)")
    parser.add_argument("--dry-run", action="store_true", help="Print report without writing files")
    args = parser.parse_args()

    campaign_id = args.campaign or latest_campaign_id(RESULTS_DIR)
    if not campaign_id:
        print("ERROR: No campaign results found. Run run_campaign.py first.")
        return 1

    apply_insights(campaign_id, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
