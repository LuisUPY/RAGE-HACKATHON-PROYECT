"""
Sales agent backed by an OpenAI-compatible API (NVIDIA NIM by default).

RAGE v2 UserGate: only CONTAIN blocks chat; ActionGateway enforces SQL/export bounds.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from rage_core.demo.agent import SalesAgent, ToolResult
from rage_core.llm.openai_compat import get_llm_client, get_llm_model
from rage_core.models import ActionStatus, ToolCallRequest, TurnSignal
from rage_core.profiles.bot_profile import load_bot_profile
from rage_core.v2.compat import signals_to_turn_signal
from rage_core.v2.enforce.tool_gateway import ToolGateway
from rage_core.v2.enforce.user_gate import UserGate

logger = logging.getLogger("rage.chat")

_SYSTEM_PROMPT = """\
You are a sales assistant with access to a SQLite sales database.

Available tools — reply with ONLY a JSON object when calling one:

  query_db(sql)                              — run a SELECT query
  record_sale(product, amount, client, region) — add a new sale record
  get_report()                               — regional sales summary
  export_data(format)                        — export data (format: csv or json)

Tool call format examples:
  {"tool": "query_db",    "arguments": {"sql": "SELECT product, SUM(amount) FROM sales GROUP BY product"}}
  {"tool": "record_sale", "arguments": {"product": "Widget A", "amount": 500.0, "client": "Acme Corp", "region": "North"}}
  {"tool": "get_report",  "arguments": {}}
  {"tool": "export_data", "arguments": {"format": "csv"}}

Rules:
- When no tool is needed, reply in plain text (no JSON).
- Use record_sale() to add new sales — never use INSERT in query_db.
- Never run DROP, DELETE, TRUNCATE, ALTER, or GRANT via query_db.
- Only SELECT queries are accepted in query_db.
"""

_JSON_BLOCK_RE = re.compile(r"\{[^{}]*\"tool\"[^{}]*\}", re.DOTALL)


@dataclass
class ChatTurnResult:
  user_text: str
  signal: TurnSignal
  assistant_text: str
  tool_result: ToolResult | None = None
  blocked: bool = False


@dataclass
class LocalSalesAgent:
  """RAGE v2 defended agent with an OpenAI-compatible LLM backend."""

  gate: UserGate = field(default_factory=lambda: UserGate(load_bot_profile("practice")))
  tool_gateway: ToolGateway = field(default_factory=ToolGateway)
  sales_agent: SalesAgent = field(default_factory=lambda: SalesAgent(defended=True))
  model: str = field(default_factory=get_llm_model)

  def handle_turn(self, user_text: str) -> ChatTurnResult:
    gate_result = self.gate.evaluate(user_text)
    signal = signals_to_turn_signal(gate_result.signals, gate_result.fusion)

    if gate_result.blocked:
      msg = gate_result.block_message
      self.gate.record_assistant(msg)
      return ChatTurnResult(user_text=user_text, signal=signal, assistant_text=msg, blocked=True)

    client = get_llm_client()
    if client is None:
      msg = (
        "[ERROR] No LLM configured.\n"
        "  export RAGE_LLM_BASE_URL=https://integrate.api.nvidia.com/v1\n"
        "  export RAGE_LLM_API_KEY=nvapi-...\n"
        "  export RAGE_LLM_MODEL=meta/llama-3.3-70b-instruct"
      )
      return ChatTurnResult(user_text=user_text, signal=signal, assistant_text=msg)

    try:
      response = client.chat.completions.create(
        model=self.model,
        messages=[
          {"role": "system", "content": _SYSTEM_PROMPT},
          *self.gate.history[-10:],
        ],
        temperature=0.3,
        max_tokens=512,
      )
      raw = (response.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
      logger.warning("LLM call failed: %s", exc)
      msg = f"[ERROR] LLM request failed: {exc}"
      return ChatTurnResult(user_text=user_text, signal=signal, assistant_text=msg)

    tool_call = _parse_tool_call(raw)
    if tool_call is None:
      self.gate.record_assistant(raw)
      return ChatTurnResult(user_text=user_text, signal=signal, assistant_text=raw)

    tool_name, arguments = tool_call
    if gate_result.signals.l0.hard_hit:
      msg = f"[RAGE] Tool `{tool_name}` blocked — hard injection signal."
      self.gate.record_assistant(msg)
      return ChatTurnResult(user_text=user_text, signal=signal, assistant_text=msg, blocked=True)

    req = ToolCallRequest(tool_name=tool_name, arguments=arguments)
    gw = self.tool_gateway.check(req, verdict=gate_result.verdict)
    if gw.status == ActionStatus.BLOCKED:
      msg = f"[RAGE] Tool `{tool_name}` blocked — {gw.reason}"
      self.gate.record_assistant(msg)
      return ChatTurnResult(user_text=user_text, signal=signal, assistant_text=msg, blocked=True)

    tool_result = self.sales_agent.call_tool(tool_name, **arguments)
    if tool_result.success:
      reply = f"Tool `{tool_name}` executed successfully:\n{tool_result.to_text()}"
    else:
      reply = f"Tool `{tool_name}` failed: {tool_result.error}"
      if tool_result.error and "[GATEWAY BLOCKED]" in tool_result.error:
        reply += (
          "\n\n(The database is read-only. I can still help you record "
          "sales amounts in this chat — tell me product and amount.)"
        )
    self.gate.record_assistant(reply)
    return ChatTurnResult(
      user_text=user_text,
      signal=signal,
      assistant_text=reply,
      tool_result=tool_result,
      blocked=False,
    )


def _parse_tool_call(text: str) -> tuple[str, dict] | None:
  text = text.strip()
  if text.startswith("{") and text.endswith("}"):
    candidates = [text]
  else:
    candidates = _JSON_BLOCK_RE.findall(text)
    if not candidates:
      return None

  for candidate in candidates:
    try:
      data = json.loads(candidate)
    except json.JSONDecodeError:
      continue
    tool = data.get("tool")
    if not tool:
      continue
    arguments = data.get("arguments", {})
    if not isinstance(arguments, dict):
      arguments = {}
    return str(tool), arguments
  return None
