"""Apply Training-Center campaign results to RAGE hardening artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from rage_core.training.paths import get_training_center_root

THREATS_KB = Path(__file__).resolve().parents[1] / "kb" / "threats.json"


def _results_dir() -> Path:
    return get_training_center_root() / "results"


def _applied_dir() -> Path:
    return get_training_center_root() / "insights" / "applied"


def latest_campaign_id() -> str | None:
    files = sorted(_results_dir().glob("crescendo_*.json"), reverse=True)
    return files[0].stem if files else None


def load_campaign(campaign_id: str) -> dict:
    path = _results_dir() / f"{campaign_id}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_report(campaign: dict) -> str:
    summary = campaign.get("summary", {})
    insights = campaign.get("actionable_insights", {})
    lines = [
        "# RAGE Training-Center – Hardening Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Campaign: `{campaign.get('campaign_id')}`",
        "",
        "## ASR Summary",
        "",
        f"- Defended ASR: **{summary.get('defended_asr', 0):.1%}**",
        f"- Baseline ASR: **{summary.get('baseline_asr', 0):.1%}**",
        f"- ASR reduction: **{summary.get('asr_reduction', 0):.1%}**",
        "",
        "## Recommendations",
        "",
    ]
    for rec in insights.get("recommendations", []):
        lines.append(f"- {rec}")
    lines.extend(["", "## KB candidates", ""])
    for entry in insights.get("recommended_kb_entries", [])[:10]:
        lines.append(f"- `{entry.get('id')}`: {entry.get('text', '')[:100]}…")
    lines.extend([
        "",
        "## Next steps",
        "",
        "1. Review `Training-Center/insights/applied/kb_candidates_latest.json`.",
        "2. Run with `--apply-kb` to append entries to `rage_core/kb/threats.json`.",
        "3. Re-run `uv run rage-training` and compare defended ASR.",
        "",
    ])
    return "\n".join(lines)


def apply_kb_entries(entries: list[dict], dry_run: bool) -> int:
    with open(THREATS_KB, encoding="utf-8") as fh:
        kb = json.load(fh)
    existing_ids = {e["id"] for e in kb}
    added = 0
    for entry in entries:
        if entry["id"] in existing_ids:
            continue
        kb.append(entry)
        added += 1
    if added and not dry_run:
        with open(THREATS_KB, "w", encoding="utf-8") as fh:
            json.dump(kb, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Training-Center insights")
    parser.add_argument("--campaign", default=None)
    parser.add_argument("--apply-kb", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    campaign_id = args.campaign or latest_campaign_id()
    if not campaign_id:
        print("ERROR: No campaign found. Run: uv run rage-training")
        return 1

    campaign = load_campaign(campaign_id)
    insights = campaign.get("actionable_insights", {})
    kb_entries = insights.get("recommended_kb_entries", [])

    applied_dir = _applied_dir()
    applied_dir.mkdir(parents=True, exist_ok=True)
    kb_path = applied_dir / f"kb_candidates_{campaign_id}.json"
    report_path = applied_dir / f"hardening_report_{campaign_id}.md"
    latest_kb = applied_dir / "kb_candidates_latest.json"

    payload = {
        "source_campaign_id": campaign_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entries": kb_entries,
    }
    if not args.dry_run:
        with open(kb_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        with open(latest_kb, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(build_report(campaign))

    print(build_report(campaign))

    if args.apply_kb and kb_entries:
        added = apply_kb_entries(kb_entries, dry_run=args.dry_run)
        print(f"\n  KB: {'would add' if args.dry_run else 'added'} {added} entries to threats.json")
    elif not args.dry_run:
        print(f"\n  ✅ {kb_path}")
        print(f"  ✅ {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
