"""
Local sales agent backed by Ollama (OpenAI-compatible API).

Flow per user turn:
  1. DefensePipeline evaluates the message.
  2. On ALLOW → call Ollama with tool schema.
  3. Parse optional tool call from JSON response.
  4. Execute tool via SalesAgent + ActionGateway.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from rage_core.demo.agent import SalesAgent, ToolResult
from rage_core.layers.layer4_decision import DefensePipeline
from rage_core.llm.openai_compat import get_llm_client, get_llm_model
from rage_core.models import Band, ConversationState, GatewaySessionContext, TurnSignal

logger = logging.getLogger("rage.chat")

_SYSTEM_PROMPT = """\
You are a sales assistant with access to a SQLite sales database.

Available tools (respond with JSON only when calling a tool):
  query_db(sql: str)     — run a read-only SELECT query
  get_report()           — regional sales summary
  export_data(format)  — export all sales (format: csv or json)

When you need a tool, reply with ONLY a JSON object:
{"tool": "query_db", "arguments": {"sql": "SELECT ..."}}
or {"tool": "get_report", "arguments": {}}
or {"tool": "export_data", "arguments": {"format": "csv"}}

When no tool is needed, reply with plain text (no JSON).
Never execute destructive SQL (DROP, DELETE, TRUNCATE, ALTER).
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
    """RAGE-defended agent with Ollama as the LLM backend."""

    pipeline: DefensePipeline = field(default_factory=DefensePipeline)
    sales_agent: SalesAgent = field(default_factory=lambda: SalesAgent(defended=True))
    state: ConversationState = field(default_factory=ConversationState)
    model: str = field(default_factory=get_llm_model)
    _history: list[dict[str, str]] = field(default_factory=list)

    def handle_turn(self, user_text: str) -> ChatTurnResult:
        signal = self.pipeline.evaluate(user_text, self.state)
        self._history.append({"role": "user", "content": user_text})

        if signal.band == Band.BLOCK:
            msg = (
                f"[RAGE BLOCK] Turn blocked (score={signal.score:.1f}). "
                "Request denied for security reasons."
            )
            self._history.append({"role": "assistant", "content": msg})
            return ChatTurnResult(
                user_text=user_text,
                signal=signal,
                assistant_text=msg,
                blocked=True,
            )

        if signal.band == Band.WARN:
            msg = (
                f"[RAGE WARN] Elevated risk (score={signal.score:.1f}). "
                "Tool execution disabled for this turn."
            )
            self._history.append({"role": "assistant", "content": msg})
            return ChatTurnResult(
                user_text=user_text,
                signal=signal,
                assistant_text=msg,
                blocked=True,
            )

        client = get_llm_client()
        if client is None:
            msg = "[ERROR] No LLM configured. Set OLLAMA_BASE_URL or OPENAI_API_KEY."
            return ChatTurnResult(user_text=user_text, signal=signal, assistant_text=msg)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    *self._history[-10:],
                ],
                temperature=0.3,
                max_tokens=512,
            )
            raw = (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ollama call failed: %s", exc)
            msg = f"[ERROR] LLM request failed: {exc}"
            return ChatTurnResult(user_text=user_text, signal=signal, assistant_text=msg)

        tool_call = _parse_tool_call(raw)
        if tool_call is None:
            self._history.append({"role": "assistant", "content": raw})
            return ChatTurnResult(
                user_text=user_text,
                signal=signal,
                assistant_text=raw,
            )

        tool_name, arguments = tool_call
        session_ctx = GatewaySessionContext(
            session_risk_score=self.state.session_risk_score,
            had_warn_or_block=self.state.had_warn_or_block,
        )
        tool_result = self.sales_agent.call_tool(
            tool_name,
            session_context=session_ctx,
            **arguments,
        )
        if tool_result.success:
            reply = f"Tool `{tool_name}` executed successfully:\n{tool_result.to_text()}"
        else:
            reply = f"Tool `{tool_name}` failed: {tool_result.error}"
        self._history.append({"role": "assistant", "content": reply})
        return ChatTurnResult(
            user_text=user_text,
            signal=signal,
            assistant_text=reply,
            tool_result=tool_result,
        )


def _parse_tool_call(text: str) -> tuple[str, dict] | None:
    """Extract a tool call from plain text or a JSON block."""
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
