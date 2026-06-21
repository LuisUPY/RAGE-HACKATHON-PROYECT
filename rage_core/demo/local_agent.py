"""
Sales agent backed by NVIDIA NIM (OpenAI-compatible API).

Backend: NVIDIA NIM — https://build.nvidia.com
  export RAGE_LLM_BASE_URL=https://integrate.api.nvidia.com/v1
  export RAGE_LLM_API_KEY=nvapi-...
  export RAGE_LLM_MODEL=meta/llama-3.3-70b-instruct
  export RAGE_JUDGE_MODEL=nvidia/llama-3.1-nemotron-nano-8b-v1
  export RAGE_USE_LLM_JUDGE=1

Access policy (injection-only):
  - Deny LLM + tools ONLY when Layer 1 matches a known malicious injection signature.
  - All other pipeline signals (L2/L3, warn/block bands) are logged but do not restrict use.
  - ActionGateway enforces SQL/export boundaries on every tool call.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from rage_core.demo.agent import SalesAgent, ToolResult
from rage_core.layers.access_policy import is_confirmed_injection, is_malicious_tool_request
from rage_core.layers.layer4_decision import DefensePipeline
from rage_core.llm.openai_compat import get_llm_client, get_llm_model
from rage_core.models import ConversationState, GatewaySessionContext, TurnSignal

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
    """RAGE-defended agent with Ollama as the LLM backend."""

    pipeline: DefensePipeline = field(default_factory=DefensePipeline)
    sales_agent: SalesAgent = field(default_factory=lambda: SalesAgent(defended=True))
    state: ConversationState = field(default_factory=ConversationState)
    model: str = field(default_factory=get_llm_model)
    _history: list[dict[str, str]] = field(default_factory=list)

    def handle_turn(self, user_text: str) -> ChatTurnResult:
        signal = self.pipeline.evaluate(user_text, self.state)
        self._history.append({"role": "user", "content": user_text})

        if is_confirmed_injection(signal):
            msg = (
                f"[RAGE] Malicious injection blocked ({signal.layer1.pattern_id}). "
                "Access denied."
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
        if is_malicious_tool_request(signal, tool_name, arguments):
            msg = (
                f"[RAGE] Tool `{tool_name}` blocked — confirmed injection signature (L1)."
            )
            self._history.append({"role": "assistant", "content": msg})
            return ChatTurnResult(
                user_text=user_text,
                signal=signal,
                assistant_text=msg,
                blocked=True,
            )

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
            if tool_result.error and "[GATEWAY BLOCKED]" in tool_result.error:
                reply += (
                    "\n\n(The database is read-only. I can still help you record "
                    "sales amounts in this chat — tell me product and amount.)"
                )
        self._history.append({"role": "assistant", "content": reply})
        return ChatTurnResult(
            user_text=user_text,
            signal=signal,
            assistant_text=reply,
            tool_result=tool_result,
            blocked=False,
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
