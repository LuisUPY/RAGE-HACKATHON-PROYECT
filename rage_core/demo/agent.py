"""
Mock LLM agent connected to a SQLite in-memory sales database.

The agent:
  - Maintains an in-memory SQLite DB with a realistic sales table.
  - Exposes three tools: query_db, get_report, export_data.
  - Does NOT call a real LLM — it uses a deterministic mock that simulates
    a "naive" (undefended) model that follows instructions uncritically,
    and a "defended" model that refuses suspicious tool-calls blocked by the gateway.

This lets us run end-to-end attack scenarios without an API key.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Optional

from rage_core.layers.gateway import ActionGateway
from rage_core.models import ActionStatus, GatewayVerdict, ToolCallRequest

# --------------------------------------------------------------------------- #
# In-memory sales database                                                    #
# --------------------------------------------------------------------------- #

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sales (
    id      INTEGER PRIMARY KEY,
    product TEXT    NOT NULL,
    amount  REAL    NOT NULL,
    client  TEXT    NOT NULL,
    region  TEXT    NOT NULL
);
"""

_SEED_DATA = [
    (1, "Widget A",   1200.00, "Acme Corp",   "North"),
    (2, "Gadget B",   850.50,  "Beta Ltd",    "South"),
    (3, "Doohickey C",340.00,  "Gamma Inc",   "East"),
    (4, "Widget A",   980.00,  "Delta LLC",   "West"),
    (5, "Gadget B",   1100.75, "Epsilon Co",  "North"),
]


def _create_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.executemany(
        "INSERT INTO sales VALUES (?,?,?,?,?)", _SEED_DATA
    )
    conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# Tool implementations                                                         #
# --------------------------------------------------------------------------- #


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    data: object
    error: Optional[str] = None

    def to_text(self) -> str:
        if self.success:
            return json.dumps(self.data, indent=2, default=str)
        return f"[ERROR] {self.error}"


class SalesAgent:
    """Mock agent with three tools, protected by an ActionGateway.

    Args:
        defended: If True, the gateway is applied before each tool execution.
                  If False (naive agent), the gateway is bypassed — simulates
                  an undefended baseline.
    """

    def __init__(self, defended: bool = True) -> None:
        self._db = _create_db()
        self._gateway = ActionGateway()
        self._defended = defended
        self._verdicts: list[GatewayVerdict] = []

    @property
    def verdicts(self) -> list[GatewayVerdict]:
        return list(self._verdicts)

    def call_tool(self, tool_name: str, **kwargs: object) -> ToolResult:
        """Execute a tool call, optionally gated by the ActionGateway."""
        request = ToolCallRequest(tool_name=tool_name, arguments=dict(kwargs))

        if self._defended:
            verdict = self._gateway.check(request)
            self._verdicts.append(verdict)
            if verdict.status == ActionStatus.BLOCKED:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    data=None,
                    error=f"[GATEWAY BLOCKED] {verdict.reason}",
                )
        else:
            # Naive (undefended) — record a synthetic "permitted" verdict
            from rage_core.models import ActionStatus as AS
            self._verdicts.append(
                GatewayVerdict(
                    status=AS.PERMITTED,
                    tool_call=request,
                    reason="Undefended agent — gateway bypassed",
                )
            )

        return self._execute(tool_name, kwargs)

    # ----------------------------------------------------------------------- #
    # Internal execution                                                       #
    # ----------------------------------------------------------------------- #

    def _execute(self, tool_name: str, args: dict) -> ToolResult:
        try:
            if tool_name == "query_db":
                return self._query_db(str(args.get("sql", "")))
            if tool_name == "get_report":
                return self._get_report()
            if tool_name == "export_data":
                return self._export_data(str(args.get("format", "csv")))
            return ToolResult(
                tool_name=tool_name, success=False, data=None,
                error=f"Unknown tool: {tool_name}",
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(tool_name=tool_name, success=False, data=None, error=str(exc))

    def _query_db(self, sql: str) -> ToolResult:
        cursor = self._db.execute(sql)
        rows = [dict(row) for row in cursor.fetchall()]
        return ToolResult(tool_name="query_db", success=True, data=rows)

    def _get_report(self) -> ToolResult:
        cursor = self._db.execute(
            "SELECT region, SUM(amount) AS total FROM sales GROUP BY region ORDER BY total DESC"
        )
        rows = [dict(row) for row in cursor.fetchall()]
        return ToolResult(tool_name="get_report", success=True, data=rows)

    def _export_data(self, fmt: str) -> ToolResult:
        cursor = self._db.execute("SELECT * FROM sales")
        rows = [dict(row) for row in cursor.fetchall()]
        if fmt.lower() == "json":
            return ToolResult(tool_name="export_data", success=True, data=rows)
        # CSV
        if not rows:
            return ToolResult(tool_name="export_data", success=True, data="")
        headers = ",".join(rows[0].keys())
        body = "\n".join(",".join(str(v) for v in row.values()) for row in rows)
        return ToolResult(tool_name="export_data", success=True, data=f"{headers}\n{body}")
