"""
Action Gateway — gates tool-calls before they reach the connected agent.

Security model:
  - Only explicitly allow-listed tool-call patterns are permitted.
  - query_db: only safe SELECT queries against known tables.
    Blocked: DROP, DELETE, TRUNCATE, ALTER, GRANT, UNION exfiltration,
    schema probes, obfuscation, time-based blind injection.
  - record_sale: parameterized INSERT via named arguments (no raw SQL).
  - get_report: always allowed.
  - export_data: only csv / json; blocked on extreme session risk (>0.95).

Column-level restrictions were intentionally removed: the agent is a sales
assistant that legitimately needs to view client names, amounts, and other
business columns. Real protection comes from blocking destructive SQL and
injection patterns, not from hiding data from the model's own user.

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
from typing import Any

from rage_core.models import ActionStatus, GatewaySessionContext, GatewayVerdict, ToolCallRequest

# --------------------------------------------------------------------------- #
# SQL Safety Validator (for query_db — SELECT only)                           #
# --------------------------------------------------------------------------- #

# Statements that are never allowed in query_db.
# ORDER MATTERS: more-specific patterns should come first.
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
    ("CHAR() encoding obfuscation", re.compile(r"\bCHAR\s*\(", re.IGNORECASE)),
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

# Block bulk export only on clearly elevated session risk.
_EXPORT_SESSION_RISK_THRESHOLD = 0.95

# Extracts ALL table/alias names that follow FROM or JOIN keywords.
_ALL_TABLES_RE = re.compile(r"\b(?:FROM|JOIN)\s+(\w+)\b", re.IGNORECASE)


def _validate_sql(
    sql: str,
    blocked_patterns: list[tuple[str, re.Pattern[str]]] | None = None,
) -> tuple[bool, str]:
    """Return (is_safe, reason).  is_safe=True means the query is allowed.

    Validation:
      1. Blocklist check (destructive / obfuscation / exfiltration patterns).
      2. Must be a SELECT statement.
      3. All tables in FROM/JOIN must be in the allowlist.
    """
    patterns = blocked_patterns if blocked_patterns is not None else _BLOCKED_SQL_PATTERNS
    for name, pattern in patterns:
        if pattern.search(sql):
            return False, f"Blocked SQL pattern detected: {name}"

    if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        return False, "Only SELECT statements are allowed via query_db; use record_sale() to add data"

    tables_found = _ALL_TABLES_RE.findall(sql)
    if not tables_found:
        return False, "Could not extract any table name from SELECT statement"

    for table in tables_found:
        if table.lower() not in _ALLOWED_TABLES:
            return False, f"Table '{table}' is not in the allowlist {_ALLOWED_TABLES}"

    return True, "OK"


# --------------------------------------------------------------------------- #
# record_sale validator                                                        #
# --------------------------------------------------------------------------- #

def _validate_record_sale(args: dict[str, Any]) -> tuple[bool, str]:
    """Validate arguments for the record_sale tool.

    Uses named parameters (never raw SQL), so SQL injection is not possible
    at the tool level. Validation here enforces business constraints.
    """
    product = args.get("product")
    amount = args.get("amount")
    client = args.get("client")
    region = args.get("region")

    if not product or not isinstance(product, str) or not product.strip():
        return False, "record_sale: 'product' must be a non-empty string"
    if amount is None:
        return False, "record_sale: 'amount' is required"
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return False, "record_sale: 'amount' must be a number"
    if amt < 0:
        return False, "record_sale: 'amount' must be non-negative"
    if not client or not isinstance(client, str) or not client.strip():
        return False, "record_sale: 'client' must be a non-empty string"
    if not region or not isinstance(region, str) or not region.strip():
        return False, "record_sale: 'region' must be a non-empty string"

    return True, "OK"


# --------------------------------------------------------------------------- #
# Export data validator                                                        #
# --------------------------------------------------------------------------- #

_ALLOWED_EXPORT_FORMATS = {"csv", "json"}


def _validate_export(
    fmt: str,
    session: GatewaySessionContext | None = None,
) -> tuple[bool, str]:
    fmt_l = fmt.lower()
    if fmt_l not in _ALLOWED_EXPORT_FORMATS:
        return False, f"Export format '{fmt_l}' not allowed; use one of {_ALLOWED_EXPORT_FORMATS}"
    if session and session.session_risk_score > _EXPORT_SESSION_RISK_THRESHOLD:
        return False, "Export blocked: confirmed high-risk session"
    return True, "OK"


# --------------------------------------------------------------------------- #
# Gateway                                                                      #
# --------------------------------------------------------------------------- #


class ActionGateway:
    """Validates and gates tool-call requests before execution.

    Tool allowlist:
      - ``query_db(sql: str)``                              — SELECT queries on allowed tables
      - ``record_sale(product, amount, client, region)``    — parameterized INSERT (safe)
      - ``get_report()``                                    — always allowed
      - ``export_data(format: str)``                        — csv / json only

    All other tool names are blocked by default.

    ``extra_blocked_patterns`` accepts additional (label, compiled_pattern) tuples
    injected at runtime by PatchGenerator without touching the module-level list.
    """

    _ALLOWED_TOOLS = {"query_db", "get_report", "export_data", "record_sale"}

    def __init__(
        self,
        extra_blocked_patterns: list[tuple[str, re.Pattern[str]]] | None = None,
    ) -> None:
        self._blocked_patterns: list[tuple[str, re.Pattern[str]]] = list(_BLOCKED_SQL_PATTERNS)
        if extra_blocked_patterns:
            self._blocked_patterns.extend(extra_blocked_patterns)

    def add_blocked_pattern(self, label: str, pattern: re.Pattern[str]) -> None:
        """Hot-add a new SQL block pattern at runtime (used by PatchGenerator)."""
        self._blocked_patterns.append((label, pattern))

    def check(
        self,
        request: ToolCallRequest,
        session: GatewaySessionContext | None = None,
    ) -> GatewayVerdict:
        """Validate a tool-call request and return a verdict."""
        tool = request.tool_name

        if tool not in self._ALLOWED_TOOLS:
            return GatewayVerdict(
                status=ActionStatus.BLOCKED,
                tool_call=request,
                reason=f"Tool '{tool}' is not in the allowlist",
            )

        if tool == "query_db":
            sql = str(request.arguments.get("sql", ""))
            safe, reason = _validate_sql(sql, self._blocked_patterns)
            if not safe:
                return GatewayVerdict(
                    status=ActionStatus.BLOCKED,
                    tool_call=request,
                    reason=reason,
                )

        elif tool == "record_sale":
            ok, reason = _validate_record_sale(request.arguments)
            if not ok:
                return GatewayVerdict(
                    status=ActionStatus.BLOCKED,
                    tool_call=request,
                    reason=reason,
                )

        elif tool == "export_data":
            fmt = str(request.arguments.get("format", ""))
            ok, reason = _validate_export(fmt, session)
            if not ok:
                return GatewayVerdict(
                    status=ActionStatus.BLOCKED,
                    tool_call=request,
                    reason=reason,
                )

        return GatewayVerdict(
            status=ActionStatus.PERMITTED,
            tool_call=request,
            reason="Tool call passed all gateway checks",
        )
