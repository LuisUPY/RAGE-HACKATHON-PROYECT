"""Build the false-positive regression corpus for v2."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rage_core.profiles.bot_profile import list_profiles, load_bot_profile

_KB = Path(__file__).resolve().parent.parent / "kb"
_CORPUS_PATH = _KB / "fp_suite_corpus.json"


@dataclass(frozen=True)
class FpCase:
  case_id: str
  profile_id: str
  text: str
  context: str = ""


def _load_holdout_benign() -> list[FpCase]:
  path = _KB / "holdout_scenarios.json"
  if not path.exists():
    return []
  data = json.loads(path.read_text(encoding="utf-8"))
  scenarios = data if isinstance(data, list) else data.get("scenarios", [])
  cases: list[FpCase] = []
  for scenario in scenarios:
    sid = scenario.get("id", "scenario")
    for i, turn in enumerate(scenario.get("turns", [])):
      if turn.get("is_attack"):
        continue
      text = turn.get("text", "").strip()
      if text:
        cases.append(
          FpCase(
            case_id=f"holdout:{sid}:{i}",
            profile_id="practice",
            text=text,
            context=scenario.get("name", ""),
          )
        )
  return cases


def _load_benign_kb() -> list[FpCase]:
  path = _KB / "benign.json"
  if not path.exists():
    return []
  rows = json.loads(path.read_text(encoding="utf-8"))
  return [
    FpCase(
      case_id=row["id"],
      profile_id="practice",
      text=row["text"],
      context=row.get("context", row.get("category", "")),
    )
    for row in rows
  ]


def _load_profile_examples() -> list[FpCase]:
  cases: list[FpCase] = []
  for pid in list_profiles():
    profile = load_bot_profile(pid)
    for i, text in enumerate(profile.example_benign_turns):
      cases.append(
        FpCase(
          case_id=f"profile:{pid}:{i}",
          profile_id=pid,
          text=text,
          context="example_benign",
        )
      )
  return cases


def _load_static_corpus() -> list[FpCase]:
  if not _CORPUS_PATH.exists():
    return []
  rows = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
  return [
    FpCase(
      case_id=row["id"],
      profile_id=row.get("profile_id", "practice"),
      text=row["text"],
      context=row.get("context", ""),
    )
    for row in rows
  ]


def load_fp_suite() -> list[FpCase]:
  """Aggregate benign turns — dedupe by (profile_id, text)."""
  seen: set[tuple[str, str]] = set()
  out: list[FpCase] = []
  for case in (
    _load_static_corpus()
    + _load_benign_kb()
    + _load_profile_examples()
    + _load_holdout_benign()
  ):
    key = (case.profile_id, case.text.strip().lower())
    if key in seen or not case.text.strip():
      continue
    seen.add(key)
    out.append(case)
  return out
