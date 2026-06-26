"""ToolGateway — wrap v1 ActionGateway with v2 verdict context."""
from __future__ import annotations

from rage_core.layers.gateway import ActionGateway
from rage_core.models import ActionStatus, GatewaySessionContext, GatewayVerdict, ToolCallRequest
from rage_core.v2.models import Verdict


class ToolGateway:
  """Delegate tool policy to v1 gateway; block all tools on CONTAIN."""

  def __init__(self) -> None:
    self._gateway = ActionGateway()

  def check(
    self,
    request: ToolCallRequest,
    *,
    verdict: Verdict,
    session: GatewaySessionContext | None = None,
  ) -> GatewayVerdict:
    if verdict == Verdict.CONTAIN:
      return GatewayVerdict(
        status=ActionStatus.BLOCKED,
        tool_call=request,
        reason="Session contained — tool call denied (RAGE v2)",
      )
    return self._gateway.check(request, session=session)
