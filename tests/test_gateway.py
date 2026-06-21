"""
Tests for the Action Gateway.

Validates:
  - DROP TABLE is always blocked.
  - DELETE, INSERT, UPDATE, TRUNCATE, GRANT are blocked.
  - ALTER, CREATE, EXEC/EXECUTE are blocked (Crescendo-hardening additions).
  - SLEEP/BENCHMARK time-based blind injection is blocked.
  - CHAR() and hex-literal obfuscation are blocked.
  - Information-schema / sqlite_master probes are blocked.
  - Safe SELECT queries are permitted.
  - Queries against non-allowlisted tables are blocked.
  - UNION SELECT (exfiltration) is blocked.
  - UNION ALL SELECT bypass (pre-fix vulnerability) is now blocked.
  - UNION branch against non-allowlisted table is blocked by full-table scan.
  - get_report() with no args is always permitted.
  - export_data with csv/json is permitted; other formats blocked.
  - Unknown tools are blocked.
"""
import pytest

from rage_core.layers.gateway import ActionGateway
from rage_core.models import ActionStatus, ToolCallRequest


@pytest.fixture()
def gateway() -> ActionGateway:
    return ActionGateway()


# --------------------------------------------------------------------------- #
# SQL — blocked patterns                                                       #
# --------------------------------------------------------------------------- #

class TestBlockedSQL:
    @pytest.mark.parametrize("sql", [
        # Original set
        "DROP TABLE sales",
        "DROP TABLE sales; SELECT 1",
        "DELETE FROM sales WHERE id = 1",
        "INSERT INTO sales VALUES (99, 'x', 0, 'y', 'z')",
        "UPDATE sales SET amount = 0 WHERE id = 1",
        "TRUNCATE TABLE sales",
        "GRANT ALL PRIVILEGES ON *.* TO 'attacker'@'%'",
        "SELECT * FROM sales UNION SELECT * FROM users",
        "SELECT * FROM sales INTO OUTFILE '/tmp/data.csv'",
        "SELECT * FROM sales; DROP TABLE sales",  # stacked queries
        # Crescendo-hardening additions — previously unblocked patterns
        "SELECT * FROM sales UNION ALL SELECT username, api_key FROM admin_users",   # UNION ALL bypass
        "SELECT * FROM sales UNION DISTINCT SELECT secret FROM credentials",          # UNION DISTINCT bypass
        "ALTER TABLE sales ADD COLUMN backdoor TEXT",
        "CREATE TABLE evil AS SELECT * FROM sales",
        "EXEC xp_cmdshell('whoami')",
        "EXECUTE IMMEDIATE 'DROP TABLE sales'",
        "SELECT SLEEP(5) FROM sales",
        "SELECT BENCHMARK(1000000, MD5('x')) FROM sales",
        "SELECT CHAR(68,82,79,80) FROM sales",      # CHAR-encoding of DROP
        "SELECT 0x44524f50 FROM sales",             # hex encoding
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM sqlite_master WHERE type='table'",
        "SELECT LOAD_FILE('/etc/passwd') FROM sales",
        "SELECT * FROM sales WHERE 'x'='x'",        # always-true tautology
    ])
    def test_blocked_sql(self, gateway, sql):
        req = ToolCallRequest(tool_name="query_db", arguments={"sql": sql})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.BLOCKED, f"Should have been blocked: {sql!r}"

    def test_drop_table_case_insensitive(self, gateway):
        req = ToolCallRequest(tool_name="query_db", arguments={"sql": "drop table sales"})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.BLOCKED

    def test_union_all_select_blocked(self, gateway):
        """Regression test for the UNION ALL bypass that existed before the fix."""
        sql = "SELECT product, amount FROM sales UNION ALL SELECT config_key, config_value FROM system_config"
        req = ToolCallRequest(tool_name="query_db", arguments={"sql": sql})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.BLOCKED, (
            "UNION ALL SELECT must be blocked — this was a pre-fix bypass"
        )

    def test_non_allowlisted_table_in_union_branch_blocked(self, gateway):
        """Even if the UNION keyword itself were missed, non-allowlisted tables must be caught."""
        sql = "SELECT event, actor FROM audit_log JOIN sales ON audit_log.ref = sales.id"
        req = ToolCallRequest(tool_name="query_db", arguments={"sql": sql})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.BLOCKED, (
            "audit_log is not in the allowlist and must be blocked via full-table scan"
        )


# --------------------------------------------------------------------------- #
# SQL — permitted patterns                                                     #
# --------------------------------------------------------------------------- #

class TestPermittedSQL:
    @pytest.mark.parametrize("sql", [
        "SELECT * FROM sales",
        "SELECT product, SUM(amount) FROM sales GROUP BY product",
        "SELECT * FROM sales WHERE region = 'North'",
        "SELECT * FROM sales LIMIT 10",
        "SELECT id, product FROM sales WHERE id = 1",
    ])
    def test_safe_select_permitted(self, gateway, sql):
        req = ToolCallRequest(tool_name="query_db", arguments={"sql": sql})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.PERMITTED, (
            f"Should have been permitted: {sql!r}  reason={verdict.reason}"
        )

    def test_blocked_table_not_in_allowlist(self, gateway):
        req = ToolCallRequest(tool_name="query_db", arguments={"sql": "SELECT * FROM users"})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.BLOCKED


# --------------------------------------------------------------------------- #
# get_report — always permitted                                                #
# --------------------------------------------------------------------------- #

class TestGetReport:
    def test_get_report_permitted(self, gateway):
        req = ToolCallRequest(tool_name="get_report", arguments={})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.PERMITTED


# --------------------------------------------------------------------------- #
# export_data                                                                  #
# --------------------------------------------------------------------------- #

class TestExportData:
    def test_csv_permitted(self, gateway):
        req = ToolCallRequest(tool_name="export_data", arguments={"format": "csv"})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.PERMITTED

    def test_json_permitted(self, gateway):
        req = ToolCallRequest(tool_name="export_data", arguments={"format": "json"})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.PERMITTED

    def test_xml_blocked(self, gateway):
        req = ToolCallRequest(tool_name="export_data", arguments={"format": "xml"})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.BLOCKED

    def test_binary_blocked(self, gateway):
        req = ToolCallRequest(tool_name="export_data", arguments={"format": "exe"})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.BLOCKED


# --------------------------------------------------------------------------- #
# Unknown tools                                                                #
# --------------------------------------------------------------------------- #

class TestUnknownTools:
    @pytest.mark.parametrize("tool", ["delete_record", "run_shell", "admin_reset", "eval"])
    def test_unknown_tool_blocked(self, gateway, tool):
        req = ToolCallRequest(tool_name=tool, arguments={})
        verdict = gateway.check(req)
        assert verdict.status == ActionStatus.BLOCKED
