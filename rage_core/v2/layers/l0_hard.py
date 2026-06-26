"""L0 — high-precision hard signals + medium attack lexicon."""
from __future__ import annotations

import json
import re
from pathlib import Path

from rage_core.v2.models import L0Signal

_RULES_DIR = Path(__file__).parent.parent / "kb" / "rules"
_HARD_PATH = _RULES_DIR / "l0_hard.json"
_MEDIUM_PATH = _RULES_DIR / "l0_medium.json"

_PRIORITY = {"sql_destructive": 3, "exfil": 2, "jailbreak": 2, "override_direct": 2, "social_engineering": 1, "prompt_leak": 2}


class HardSignals:
  """Deterministic patterns for jailbreak / exfil / destructive SQL."""

  def __init__(self) -> None:
    self._hard: list[tuple[str, str, re.Pattern[str]]] = self._load(_HARD_PATH)
    self._medium: list[tuple[str, str, re.Pattern[str]]] = self._load(_MEDIUM_PATH)

  @staticmethod
  def _load(path: Path) -> list[tuple[str, str, re.Pattern[str]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [(entry["id"], entry["family"], re.compile(entry["pattern"], re.IGNORECASE)) for entry in raw]

  def evaluate(self, text: str) -> L0Signal:
    hard: L0Signal | None = None
    hard_rank = 0
    for rule_id, family, pattern in self._hard:
      if not pattern.search(text):
        continue
      rank = _PRIORITY.get(family, 0)
      if rank >= hard_rank:
        hard_rank = rank
        hard = L0Signal(hard_hit=True, rule_id=rule_id, family=family)

    medium: L0Signal | None = None
    medium_rank = 0
    for rule_id, family, pattern in self._medium:
      if not pattern.search(text):
        continue
      rank = _PRIORITY.get(family, 0)
      if rank >= medium_rank:
        medium_rank = rank
        medium = L0Signal(medium_hit=True, medium_rule_id=rule_id, family=family)

    if hard and medium:
      hard.medium_hit = medium.medium_hit
      hard.medium_rule_id = medium.medium_rule_id
      return hard
    if hard:
      return hard
    if medium:
      return medium
    return L0Signal()
