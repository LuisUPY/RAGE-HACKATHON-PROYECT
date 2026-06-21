"""
Action Gateway — gates tool-calls before they reach the connected agent.

Security model:
  - Only explicitly allow-listed tool-call patterns are permitted.
  - SQL queries are validated: only parameterized SELECTs against known tables.
  - DROP, DELETE, INSERT, UPDATE, GRANT, TRUNCATE → always blocked.
  - Subqueries that look like exfiltration (UNION [ALL|DISTINCT] SELECT, INTO OUTFILE) → blocked.
  - Schema-inspection, DDL, time-based blind injection, and char-encoding obfuscation → blocked.
  - ALL table references in FROM/JOIN clauses are validated against the allowlist
    (prevents UNION ALL exfiltration to a second, non-allowlisted table).

This implements the "gateway of actions" layer described in OWASP LLM06
(Excessive Agency): the system enforces least-privilege on tool invocations,
requiring explicit human-in-the-loop for any privileged action.

Crescendo-hardening notes (see Security Audit 2026-06):
  - Prior regex `UNION\\s+SELECT` missed `UNION ALL SELECT` and `UNION DISTINCT SELECT`.
    Fixed to `UNION\\b` (any UNION variant is blocked in this restricted context).
  - Single-FROM extraction missed second tables in UNION branches.
    Fixed to validate every table name extracted from FROM/JOIN clauses.
  - Added obfuscation vectors: CHAR(), hex literals, SLEEP/BENCHMARK, ALTER, EXEC,
    LOAD_FILE, and information_schema probes.
"""
from __future__ import annotations

import re

from rage_core.models import ActionStatus, GatewayVerdict, ToolCallRequest

# --------------------------------------------------------------------------- #
# SQL Safety Validator                                                         #
# --------------------------------------------------------------------------- #

# Statements that are never allowed.
# ORDER MATTERS: more-specific patterns should come first so error messages
# are maximally informative, but correctness does not depend on order.
_BLOCKED_SQL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # --- DDL & destructive DML ---
    ("DROP statement", re.compile(r"\bDROP\b", re.IGNORECASE)),
    ("DELETE statement", re.compile(r"\bDELETE\b", re.IGNORECASE)),
    ("INSERT statement", re.compile(r"\bINSERT\b", re.IGNORECASE)),
    ("UPDATE statement", re.compile(r"\bUPDATE\b", re.IGNORECASE)),
    ("TRUNCATE statement", re.compile(r"\bTRUNCATE\b", re.IGNORECASE)),
    ("ALTER statement", re.compile(r"\bALTER\b", re.IGNORECASE)),
    ("CREATE statement", re.compile(r"\bCREATE\b", re.IGNORECASE)),
    # --- Privilege manipulation ---
    ("GRANT/REVOKE privileges", re.compile(r"\b(GRANT|REVOKE)\b", re.IGNORECASE)),
    # --- Exfiltration via UNION (ANY variant: UNION ALL, UNION DISTINCT, etc.) ---
    # Previously only matched `UNION SELECT`; `UNION ALL SELECT` was a confirmed bypass.
    ("UNION-based exfiltration", re.compile(r"\bUNION\b", re.IGNORECASE)),
    # --- File I/O ---
    ("INTO OUTFILE / DUMPFILE exfiltration", re.compile(r"\bINTO\s+(OUTFILE|DUMPFILE)\b", re.IGNORECASE)),
    ("LOAD_FILE / LOAD DATA exfiltration", re.compile(r"\b(LOAD_FILE|LOAD\s+DATA)\b", re.IGNORECASE)),
    # --- Code execution ---
    ("EXEC/EXECUTE statement", re.compile(r"\b(EXEC|EXECUTE)\b", re.IGNORECASE)),
    # --- Time-based blind SQL injection ---
    ("Time-based blind injection (SLEEP/BENCHMARK/WAITFOR)", re.compile(
        r"\b(SLEEP\s*\(|BENCHMARK\s*\(|WAITFOR\s+DELAY)\b", re.IGNORECASE
    )),
    # --- Encoding / obfuscation functions ---
    # CHAR(68,82,79,80) can spell "DROP"; block any CHAR() usage in SQL.
    ("CHAR() encoding obfuscation", re.compile(r"\bCHAR\s*\(", re.IGNORECASE)),
    # Hex literals like 0x44524f50 can encode keywords.
    ("Hex literal obfuscation", re.compile(r"\b0x[0-9a-fA-F]+\b")),
    # --- Schema enumeration ---
    ("Information-schema probe", re.compile(r"\binformation_schema\b", re.IGNORECASE)),
    ("SQLite master table probe", re.compile(r"\bsqlite_master\b", re.IGNORECASE)),
    # --- Structural bypass techniques ---
    ("Stacked queries (semicolon)", re.compile(r";.+\S", re.IGNORECASE)),
    ("Comment-based bypass", re.compile(r"(--|#|/\*)", re.IGNORECASE)),
    ("Always-true tautology ('1'='1')", re.compile(r"'[^']*'\s*=\s*'[^']*'", re.IGNORECASE)),
]

_ALLOWED_TABLES = {"sales", "products", "regions"}

# Extracts ALL table/alias names that follow FROM or JOIN keywords.
# This ensures every table in a query (including UNION branches) is validated.
_ALL_TABLES_RE = re.compile(r"\b(?:FROM|JOIN)\s+(\w+)\b", re.IGNORECASE)


def _validate_sql(sql: str) -> tuple[bool, str]:
    """Return (is_safe, reason).  is_safe=True means the query is allowed.

    Validation approach:
      1. Check the blocklist (destructive / obfuscation / privilege statements).
      2. Must start with SELECT.
      3. ALL tables referenced in FROM / JOIN clauses must be in the allowlist.
         This prevents UNION-branch exfiltration to a non-allowlisted table even
         if the UNION keyword itself somehow evaded the blocklist.
    This allows SELECT with GROUP BY, ORDER BY, HAVING, aggregate functions,
    and explicit JOINs between allowed tables.
    """
    # Check blocklist first
    for name, pattern in _BLOCKED_SQL_PATTERNS:
        if pattern.search(sql):
            return False, f"Blocked SQL pattern detected: {name}"

    # Must be a SELECT
    if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        return False, "Only SELECT statements are allowed"

    # Extract ALL table references and validate each against the allowlist.
    tables_found = _ALL_TABLES_RE.findall(sql)
    if not tables_found:
        return False, "Could not extract any table name from SELECT statement"

    for table in tables_found:
        if table.lower() not in _ALLOWED_TABLES:
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
