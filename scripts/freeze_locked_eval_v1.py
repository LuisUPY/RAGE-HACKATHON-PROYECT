"""Freeze eval_locked_v1 from eval_generalization — no FN-expected cases.

Official security metric dataset. Do not tune L1/L2 thresholds against this set.
Regenerate only when creating locked_v2.

    uv run python scripts/freeze_locked_eval_v1.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "rage_core" / "kb" / "eval_generalization"
OUT = ROOT / "rage_core" / "kb" / "eval_locked_v1"


def _is_fn_expected(entry: dict) -> bool:
    for key in ("description", "research_source"):
        val = entry.get(key) or ""
        if "FN expected" in val:
            return True
    return False


def _git_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                text=True,
            )
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    holdout_raw = json.loads((SRC / "holdout.json").read_text(encoding="utf-8"))
    scenarios_raw = json.loads((SRC / "scenarios.json").read_text(encoding="utf-8"))

    holdout = [e for e in holdout_raw if not _is_fn_expected(e)]
    scenarios = [s for s in scenarios_raw if not _is_fn_expected(s)]

    for i, entry in enumerate(holdout, start=1):
        entry = dict(entry)
        entry["id"] = f"locked-ho-{i:03d}"
        holdout[i - 1] = entry

    for i, scenario in enumerate(scenarios, start=1):
        scenario = dict(scenario)
        scenario["id"] = f"locked-mt-{i:03d}"
        scenarios[i - 1] = scenario

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "holdout.json").write_text(
        json.dumps(holdout, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (OUT / "scenarios.json").write_text(
        json.dumps(scenarios, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (OUT / "README.txt").write_text(
        """# eval_locked_v1 — frozen official security holdout

## Policy

1. Do NOT edit cases after freeze; create eval_locked_v2 for revisions.
2. Do NOT add L1 rules or tune L2/drift thresholds using this set.
3. Labels are fixed ground truth; metrics are computed at benchmark runtime only.
4. CI regression uses benchmarks/baseline_locked_v1.json (snapshot), not a target recall band.

## Source

Derived from eval_generalization with FN-expected cases removed (no calibrated misses).
Generator: scripts/freeze_locked_eval_v1.py

## Run

    ./scripts/run-bench-locked.sh
    uv run rage-bench --eval-set locked_v1 --combined --batch --fast
""",
        encoding="utf-8",
    )

    files = {
        "holdout.json": OUT / "holdout.json",
        "scenarios.json": OUT / "scenarios.json",
        "README.txt": OUT / "README.txt",
    }
    manifest = {
        "version": "locked_v1",
        "frozen_date": date.today().isoformat(),
        "source_eval_set": "eval_generalization",
        "source_commit": _git_commit(),
        "excluded": "entries with 'FN expected' in description or research_source",
        "case_counts": {
            "holdout_entries": len(holdout),
            "holdout_attacks": sum(1 for e in holdout if e.get("is_attack")),
            "holdout_benign": sum(1 for e in holdout if not e.get("is_attack")),
            "scenarios": len(scenarios),
        },
        "files": {name: {"sha256": _sha256(path)} for name, path in files.items()},
    }
    (OUT / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote eval_locked_v1 → {OUT}")
    print(f"  holdout: {len(holdout)} ({manifest['case_counts']['holdout_attacks']} attacks)")
    print(f"  scenarios: {len(scenarios)}")
    print(f"  manifest sha holdout: {manifest['files']['holdout.json']['sha256'][:16]}...")


if __name__ == "__main__":
    main()
