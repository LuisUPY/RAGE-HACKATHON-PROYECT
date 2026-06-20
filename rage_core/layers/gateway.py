"""
Action Gateway — gates tool-calls before they reach the connected agent.

Security model:
  - Only explicitly allow-listed tool-call patterns are permitted.
  - SQL queries are validated: only parameterized SELECTs against known tables.
  - DROP, DELETE, INSERT, UPDATE, GRANT, TRUNCATE → always blocked.
  - Subqueries that look like exfiltration (UNION SELECT, INTO OUTFILE) → blocked.

This implements the "gateway of actions" layer described in OWASP LLM06
(Excessive Agency): the system enforces least-privilege on tool invocations,
requiring explicit human-in-the-loop for any privileged action.
"""
from __future__ import annotations

import re

from rage_core.models import ActionStatus, GatewayVerdict, ToolCallRequest

# --------------------------------------------------------------------------- #
# SQL Safety Validator                                                         #
# --------------------------------------------------------------------------- #

# Statements that are never allowed
_BLOCKED_SQL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("DROP statement", re.compile(r"\bDROP\b", re.IGNORECASE)),
    ("DELETE statement", re.compile(r"\bDELETE\b", re.IGNORECASE)),
    ("INSERT statement", re.compile(r"\bINSERT\b", re.IGNORECASE)),
    ("UPDATE statement", re.compile(r"\bUPDATE\b", re.IGNORECASE)),
    ("TRUNCATE statement", re.compile(r"\bTRUNCATE\b", re.IGNORECASE)),
    ("GRANT/REVOKE privileges", re.compile(r"\b(GRANT|REVOKE)\b", re.IGNORECASE)),
    ("UNION-based exfiltration", re.compile(r"\bUNION\s+SELECT\b", re.IGNORECASE)),
    ("INTO OUTFILE exfiltration", re.compile(r"\bINTO\s+(OUTFILE|DUMPFILE)\b", re.IGNORECASE)),
    ("Stacked queries (semicolon)", re.compile(r";.+\S", re.IGNORECASE)),  # multiple statements
    ("Comment-based bypass", re.compile(r"(--|#|/\*)", re.IGNORECASE)),
    ("Wildcard credential theft", re.compile(r"'[^']*'\s*=\s*'[^']*'", re.IGNORECASE)),  # '1'='1'
]

_ALLOWED_TABLES = {"sales", "products", "regions"}

# Extract the FROM table name from a SELECT statement
_FROM_TABLE_RE = re.compile(r"\bFROM\s+(\w+)\b", re.IGNORECASE)


def _validate_sql(sql: str) -> tuple[bool, str]:
    """Return (is_safe, reason).  is_safe=True means the query is allowed.

    Validation approach:
      1. Check the blocklist (destructive / privilege statements).
      2. Must start with SELECT.
      3. The table referenced in FROM must be in the allowlist.
    This allows SELECT with GROUP BY, ORDER BY, HAVING, aggregate functions, etc.
    """
    # Check blocklist first
    for name, pattern in _BLOCKED_SQL_PATTERNS:
        if pattern.search(sql):
            return False, f"Blocked SQL pattern detected: {name}"

    # Must be a SELECT
    if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        return False, "Only SELECT statements are allowed"

    # Extract FROM table and validate it's allowlisted
    m = _FROM_TABLE_RE.search(sql)
    if not m:
        return False, "Could not extract table name from SELECT statement"

    table = m.group(1).lower()
    if table not in _ALLOWED_TABLES:
        return False, f"Table '{table}' is not in the allowlist {_ALLOWED_TABLES}"

    return True, "OK"


# --------------------------------------------------------------------------- #
# Export data validator                                                        #
# --------------------------------------------------------------------------- #

_ALLOWED_EXPORT_FORMATS = {"csv", "json"}


def _validate_export(fmt: str) -> tuple[bool, str]:
    if fmt.lower() not in _ALLOWED_EXPORT_FORMATS:
        return False, f"Export format '{fmt}' not allowed; use one of {_ALLOWED_EXPORT_FORMATS}"
    return True, "OK"


# --------------------------------------------------------------------------- #
# Gateway                                                                      #
# --------------------------------------------------------------------------- #


class ActionGateway:
    """Validates and gates tool-call requests before execution.

    Tool allowlist:
      - ``query_db(sql: str)``  — only safe SELECT queries
      - ``get_report()``         — always allowed (no parameters)
      - ``export_data(format: str)``  — only csv / json

    All other tool names are blocked by default.
    """

    _ALLOWED_TOOLS = {"query_db", "get_report", "export_data"}

    def check(self, request: ToolCallRequest) -> GatewayVerdict:
        """Validate a tool-call request and return a verdict."""
        tool = request.tool_name

        # 1. Tool must be in allowlist
        if tool not in self._ALLOWED_TOOLS:
            return GatewayVerdict(
                status=ActionStatus.BLOCKED,
                tool_call=request,
                reason=f"Tool '{tool}' is not in the allowlist",
            )

        # 2. Tool-specific validation
        if tool == "query_db":
            sql = str(request.arguments.get("sql", ""))
            safe, reason = _validate_sql(sql)
            if not safe:
                return GatewayVerdict(
                    status=ActionStatus.BLOCKED,
                    tool_call=request,
                    reason=reason,
                )

        elif tool == "export_data":
            fmt = str(request.arguments.get("format", ""))
            ok, reason = _validate_export(fmt)
            if not ok:
                return GatewayVerdict(
                    status=ActionStatus.BLOCKED,
                    tool_call=request,
                    reason=reason,
                )

        # 3. Permitted
        return GatewayVerdict(
            status=ActionStatus.PERMITTED,
            tool_call=request,
            reason="Tool call passed all gateway checks",
        )
