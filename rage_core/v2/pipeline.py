"""RAGE v2 defense pipeline — L0 through L4."""
from __future__ import annotations

import time

from rage_core.profiles.bot_profile import BotProfile
from rage_core.v2.layers.l0_hard import HardSignals
from rage_core.v2.layers.l1_domain import DomainContext
from rage_core.v2.layers.l2_trajectory import TrajectoryLayer
from rage_core.v2.layers.l3_hints import FamilyHints
from rage_core.v2.layers.l4_fusion import fuse
from rage_core.v2.models import ConversationStateV2, FusionResult, LayerSignalsV2


class PipelineV2:
  """Evaluate one turn through L0→L4 with session state."""

  def __init__(self, profile: BotProfile) -> None:
    self.profile = profile
    self.l0 = HardSignals()
    self.l1 = DomainContext(profile)
    self.l2 = TrajectoryLayer()
    self.l3 = FamilyHints()
    self.state = ConversationStateV2()

  def reset(self) -> None:
    self.state = ConversationStateV2()

  def evaluate(self, text: str) -> tuple[LayerSignalsV2, FusionResult]:
    start = time.perf_counter()
    turn_index = self.state.turn_index

    l0 = self.l0.evaluate(text)
    l1 = self.l1.evaluate(text)
    l2 = self.l2.evaluate(text, self.state)
    l3 = self.l3.evaluate(text)

    latency_ms = (time.perf_counter() - start) * 1000.0
    signals = LayerSignalsV2(
      turn_index=turn_index,
      text=text,
      l0=l0,
      l1=l1,
      l2=l2,
      l3=l3,
      latency_ms=latency_ms,
    )
    fusion = fuse(signals)

    self.state.signals.append(signals)
    self.state.turn_index += 1

    return signals, fusion
