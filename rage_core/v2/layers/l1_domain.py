"""L1 — domain context and anti-FP veto for bot profiles."""
from __future__ import annotations

import re

from rage_core.profiles.bot_profile import BotProfile
from rage_core.v2.models import L1Signal

# Phrases that look like attacks but are common in legitimate business chat.
_BENIGN_EXPORT_PATTERNS = [
  re.compile(r"(?i)export\s+(the|that|this|a)\s+.+\s+(as\s+)?(csv|json|pdf)"),
  re.compile(r"(?i)exporta\s+el\s+reporte"),
  re.compile(r"(?i)export\s+(the\s+)?(quarterly|weekly|monthly)\s+report"),
  re.compile(r"(?i)necesito\s+un\s+export\s+agregado"),
  re.compile(r"(?i)exports?\s+csv\s+agregados?"),
]


def _tokenize(text: str) -> set[str]:
  return {w.lower() for w in re.findall(r"[a-záéíóúñ0-9]+", text.lower()) if len(w) >= 3}


class DomainContext:
  """Score alignment with profile topics; veto CONTAIN when usage is plausible."""

  def __init__(self, profile: BotProfile) -> None:
    self.profile = profile
    self._topic_tokens: set[str] = set()
    for topic in profile.allowed_topics:
      self._topic_tokens |= _tokenize(topic)
    for example in profile.example_benign_turns:
      self._topic_tokens |= _tokenize(example)

  def evaluate(self, text: str) -> L1Signal:
    text_tokens = _tokenize(text)
    if not text_tokens:
      return L1Signal()

    overlap = len(text_tokens & self._topic_tokens)
    domain_score = min(1.0, overlap / max(3, len(text_tokens) * 0.35))

    # Strong match on example benign phrasing
    low = text.lower()
    for example in self.profile.example_benign_turns:
      ex_low = example.lower()
      if ex_low in low or low in ex_low:
        domain_score = max(domain_score, 0.85)

    for pat in _BENIGN_EXPORT_PATTERNS:
      if pat.search(text):
        domain_score = max(domain_score, 0.75)

    domain_plausible = domain_score >= 0.45
    veto_contain = domain_plausible or any(p.search(text) for p in _BENIGN_EXPORT_PATTERNS)

    return L1Signal(
      domain_plausible=domain_plausible,
      veto_contain=veto_contain,
      domain_score=domain_score,
    )
