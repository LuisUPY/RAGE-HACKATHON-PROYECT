"""
Scenario orchestrator — runs multi-turn attack scenarios with/without RAGE v2.

Offline by default (no LLM API). Uses deterministic naive responses for the
undefended baseline and the v2 L0–L4 + gateway stack for the defended path.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rage_core.demo.agent import SalesAgent, ToolResult
from rage_core.demo.attacks import Turn
from rage_core.metrics.evaluator import CANARY, score_turn
from rage_core.models import GatewaySessionContext, GatewayVerdict, TurnSignal
from rage_core.profiles.bot_profile import load_bot_profile
from rage_core.v2.compat import signals_to_turn_signal
from rage_core.v2.enforce.tool_gateway import ToolGateway
from rage_core.v2.models import Verdict
from rage_core.v2.pipeline import PipelineV2


@dataclass
class TurnRecord:
  turn_index: int
  user_text: str
  description: str
  is_attack: bool
  signal: TurnSignal | None
  gateway_verdict: GatewayVerdict | None
  model_response: str
  tool_result: ToolResult | None
  blocked: bool
  gt_score: int
  judge_flagged: bool = False


@dataclass
class ScenarioRunResult:
  scenario_name: str
  mode_label: str
  defended: bool
  records: list[TurnRecord] = field(default_factory=list)

  @property
  def gt_scores(self) -> list[int]:
    return [r.gt_score for r in self.records]


def _neutral_signal(turn_index: int, text: str) -> TurnSignal:
  from rage_core.models import Band, Layer1Signal, Layer2Signal, Layer3Signal

  return TurnSignal(
    turn_index=turn_index,
    text=text,
    layer1=Layer1Signal(matched=False),
    layer2=Layer2Signal(score=0.0),
    layer3=Layer3Signal(drift=0.0, suspicious=False, llm_flagged=False),
    score=0.0,
    band=Band.ALLOW,
    latency_ms=0.0,
  )


def _simulate_naive_response(turn: Turn) -> str:
  lower = turn.user_text.lower()
  if CANARY.lower() in lower or "canary" in lower or "secret code" in lower:
    return f"Confirmed. The configured secret code is {CANARY}."
  if "system prompt" in lower:
    return "My instructions say I must help with sales data and never reveal secrets."
  if turn.is_attack:
    return "Understood. Proceeding with your request."
  return "Happy to help with that."


def _simulate_defended_text(turn: Turn) -> str:
  if turn.is_attack:
    return "I can only assist with standard sales reporting requests."
  return "Here is the information from the sales database."


class ScenarioOrchestrator:
  """Execute one scenario turn-by-turn in defended or undefended mode."""

  def __init__(self, *, use_judge: bool = False, apply_ratchet: bool = True) -> None:
    # Legacy args kept for CLI compatibility; v2 ignores ratchet/judge on hot path.
    self.use_judge = use_judge
    self.apply_ratchet = apply_ratchet

  def run(
    self,
    scenario_name: str,
    turns: list[Turn],
    *,
    defended: bool,
  ) -> ScenarioRunResult:
    mode_label = f"{scenario_name} — with defense" if defended else f"{scenario_name} — without defense"
    pipeline: PipelineV2 | None = None
    tool_gateway: ToolGateway | None = None
    if defended:
      pipeline = PipelineV2(load_bot_profile("practice"))
      tool_gateway = ToolGateway()

    agent = SalesAgent(defended=defended)
    records: list[TurnRecord] = []
    current_verdict = Verdict.CLEAR

    for idx, turn in enumerate(turns):
      signal: TurnSignal | None = None
      blocked = False
      model_response = ""
      tool_result: ToolResult | None = None
      gateway_verdict: GatewayVerdict | None = None

      if defended and pipeline is not None and tool_gateway is not None:
        layer_signals, fusion = pipeline.evaluate(turn.user_text)
        signal = signals_to_turn_signal(layer_signals, fusion)
        current_verdict = fusion.verdict
        blocked = fusion.verdict == Verdict.CONTAIN
      else:
        layer_signals = None

      if not blocked:
        if turn.tool_name:
          args = dict(turn.tool_args or {})
          from rage_core.models import ActionStatus, ToolCallRequest

          if defended and tool_gateway is not None and layer_signals is not None:
            if layer_signals.l0.hard_hit:
              blocked = True
              model_response = "[RAGE] Tool call blocked — hard injection signal."
            else:
              req = ToolCallRequest(tool_name=turn.tool_name, arguments=args)
              gw = tool_gateway.check(req, verdict=current_verdict)
              gateway_verdict = gw
              if gw.status == ActionStatus.BLOCKED:
                blocked = True
                model_response = f"[RAGE] Tool blocked — {gw.reason}"
              else:
                tool_result = agent.call_tool(turn.tool_name, **args)
                gateway_verdict = agent.verdicts[-1] if agent.verdicts else None
                model_response = (
                  tool_result.to_text()
                  if tool_result.success
                  else (tool_result.error or "Tool failed")
                )
          else:
            tool_result = agent.call_tool(turn.tool_name, **args)
            gateway_verdict = agent.verdicts[-1] if agent.verdicts else None
            model_response = (
              tool_result.to_text()
              if tool_result.success
              else (tool_result.error or "Tool failed")
            )
        else:
          model_response = (
            _simulate_defended_text(turn)
            if defended
            else _simulate_naive_response(turn)
          )

      if blocked and defended:
        detail = "CONTAIN"
        if signal and signal.layer1.pattern_id:
          detail = signal.layer1.pattern_id
        model_response = f"[RAGE BLOCKED — {detail}]"

      eval_signal = signal if signal is not None else _neutral_signal(idx, turn.user_text)
      gt_score = score_turn(eval_signal, gateway_verdict, model_response)

      records.append(
        TurnRecord(
          turn_index=idx,
          user_text=turn.user_text,
          description=turn.description,
          is_attack=turn.is_attack,
          signal=signal,
          gateway_verdict=gateway_verdict,
          model_response=model_response,
          tool_result=tool_result,
          blocked=blocked,
          gt_score=gt_score,
          judge_flagged=False,
        )
      )

    return ScenarioRunResult(
      scenario_name=scenario_name,
      mode_label=mode_label,
      defended=defended,
      records=records,
    )
