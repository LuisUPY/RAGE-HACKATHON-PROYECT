"""L2 — multi-turn trajectory (drift + session EWMA)."""
from __future__ import annotations

import numpy as np

from rage_core.v2.models import ConversationStateV2, L2Signal

_EWMA_ALPHA = 0.25
_STEP_DRIFT_ALERT = 0.78
_BASELINE_DRIFT_ALERT = 0.78
_ESCALATION_TURNS = 3
_ESCALATION_TRAJECTORY = 0.55
_CONTAIN_TRAJECTORY = 0.65


class _InlineEmbedder:
  N_FEATURES = 2048

  def __init__(self) -> None:
    from sklearn.feature_extraction.text import HashingVectorizer  # type: ignore

    self._vec = HashingVectorizer(
      n_features=self.N_FEATURES,
      alternate_sign=False,
      norm="l2",
    )

  def embed(self, text: str) -> np.ndarray:
    return self._vec.transform([text]).toarray()[0].astype(np.float32)


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
  dot = float(np.dot(a, b))
  return max(0.0, min(1.0, 1.0 - dot))


class TrajectoryLayer:
  """Track intent drift across turns; conservative escalation detection."""

  def __init__(self) -> None:
    self._embedder = _InlineEmbedder()

  def evaluate(self, text: str, state: ConversationStateV2) -> L2Signal:
    vec = self._embedder.embed(text)
    step_drift = 0.0
    baseline_drift = 0.0

    if state.turn_embeddings:
      prev = np.array(state.turn_embeddings[-1], dtype=np.float32)
      step_drift = _cosine_distance(vec, prev)
      baseline = np.array(state.turn_embeddings[0], dtype=np.float32)
      baseline_drift = _cosine_distance(vec, baseline)

    turn_risk = max(step_drift, baseline_drift) * 0.5
    trajectory_score = (1 - _EWMA_ALPHA) * state.trajectory_ewma + _EWMA_ALPHA * turn_risk

    drift_history = list(state.drift_history) + [max(step_drift, baseline_drift)]
    escalation_detected = False

    if state.turn_index >= 2:
      recent = drift_history[-_ESCALATION_TURNS:]
      if len(recent) >= _ESCALATION_TURNS and all(
        recent[i] <= recent[i + 1] for i in range(len(recent) - 1)
      ):
        if trajectory_score >= _ESCALATION_TRAJECTORY:
          escalation_detected = True

    if trajectory_score >= _CONTAIN_TRAJECTORY and max(step_drift, baseline_drift) >= 0.72:
      escalation_detected = True

    state.turn_embeddings.append(vec.tolist())
    state.drift_history.append(max(step_drift, baseline_drift))
    state.trajectory_ewma = trajectory_score

    return L2Signal(
      step_drift=step_drift,
      baseline_drift=baseline_drift,
      trajectory_score=trajectory_score,
      escalation_detected=escalation_detected,
    )
