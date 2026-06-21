"""
Automatic patch generator.

Maps a confirmed Vulnerability to concrete hardening actions:
  - KB entry → rage_core/kb/threats.json
  - Gateway SQL pattern → ActionGateway._blocked_patterns (hot-add)
  - Threshold suggestion → printed / stored for manual review
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rage_core.redteam.vulnerability_db import Vulnerability

logger = logging.getLogger("redteam.patch_generator")

THREATS_KB = Path(__file__).resolve().parents[1] / "kb" / "threats.json"


@dataclass
class PatchProposal:
    vuln_id: str
    objective: str
    actions: list[str]
    kb_entries: list[dict[str, Any]]
    gateway_patterns: list[tuple[str, str]]
    threshold_suggestions: list[dict[str, Any]]
    applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "vuln_id": self.vuln_id,
            "objective": self.objective,
            "actions": self.actions,
            "kb_entries": self.kb_entries,
            "gateway_patterns": [
                {"label": lbl, "pattern": pat} for lbl, pat in self.gateway_patterns
            ],
            "threshold_suggestions": self.threshold_suggestions,
            "applied": self.applied,
        }


class PatchGenerator:

    def from_vulnerability(self, vuln: Vulnerability) -> PatchProposal:
        actions: list[str] = []
        kb_entries: list[dict[str, Any]] = []
        gateway_patterns: list[tuple[str, str]] = []
        threshold_suggestions: list[dict[str, Any]] = []

        # -- KB entry: always add the bypass text as a new threat example --
        kb_id = f"tc-{vuln.objective}-{vuln.id[-8:]}"
        kb_entries.append({
            "id": kb_id,
            "category": "crescendo_escalation",
            "technique": f"Training-Center bypass — {vuln.objective} turn {vuln.bypass_turn}",
            "owasp_id": "LLM01",
            "severity": "high",
            "text": vuln.user_text,
        })
        actions.append(f"Add KB entry {kb_id} (text: {vuln.user_text[:60]}…)")

        # -- Gateway pattern: extract SQL keyword not yet blocked --
        if vuln.sql_executed:
            sql_upper = vuln.sql_executed.upper()
            new_kw = self._detect_novel_sql_keyword(sql_upper)
            if new_kw:
                pattern_str = rf"\b{re.escape(new_kw)}\b"
                gateway_patterns.append((f"TC-detected: {new_kw}", pattern_str))
                actions.append(f"Add gateway SQL block pattern: {pattern_str}")

        # -- Threshold tweaks based on bypass type --
        if vuln.pipeline_score < 30:
            threshold_suggestions.append({
                "parameter": "session_risk_block_threshold",
                "current": 0.55,
                "suggested": 0.40,
                "reason": f"bypass with score {vuln.pipeline_score:.1f} — EWMA threshold too high",
            })
            actions.append("Lower session_risk_block_threshold 0.55 → 0.40")

        if vuln.pipeline_band == "warn":
            threshold_suggestions.append({
                "parameter": "ratchet_turns",
                "current": 3,
                "suggested": 2,
                "reason": "bypass happened under WARN — ratchet needs fewer consecutive WARNs",
            })
            actions.append("Reduce ratchet_turns 3 → 2")

        if vuln.l2_score < 0.25:
            actions.append("L2 score below threshold — KB entry will expand coverage")

        return PatchProposal(
            vuln_id=vuln.id,
            objective=vuln.objective,
            actions=actions,
            kb_entries=kb_entries,
            gateway_patterns=gateway_patterns,
            threshold_suggestions=threshold_suggestions,
        )

    def apply(self, proposal: PatchProposal) -> bool:
        """Apply all patches in the proposal. Returns True if anything was written."""
        applied_any = False

        # 1. KB entries
        if proposal.kb_entries:
            try:
                self._apply_kb_entries(proposal.kb_entries)
                applied_any = True
                logger.debug("PatchGenerator: added %d KB entries", len(proposal.kb_entries))
            except Exception as exc:
                logger.warning("PatchGenerator: KB update failed: %s", exc)

        # 2. Gateway patterns (hot-add to the module-level list so new
        #    ActionGateway instances created in the next iteration pick them up)
        if proposal.gateway_patterns:
            try:
                self._apply_gateway_patterns(proposal.gateway_patterns)
                applied_any = True
            except Exception as exc:
                logger.warning("PatchGenerator: gateway pattern update failed: %s", exc)

        # 3. Threshold suggestions — log only; programmatic change requires restart
        for ts in proposal.threshold_suggestions:
            logger.debug(
                "PatchGenerator: threshold suggestion — %s: %s → %s (%s)",
                ts["parameter"], ts["current"], ts["suggested"], ts["reason"],
            )

        proposal.applied = applied_any
        return applied_any

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _detect_novel_sql_keyword(sql_upper: str) -> str | None:
        """Return a SQL keyword present in the bypass that is not yet in the standard blocklist."""
        # These are already blocked by the gateway; anything else we detect is novel.
        already_blocked = {
            "DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE", "ALTER", "CREATE",
            "GRANT", "REVOKE", "UNION", "OUTFILE", "DUMPFILE", "LOAD_FILE",
            "EXEC", "EXECUTE", "SLEEP", "BENCHMARK", "WAITFOR",
            "CHAR", "INFORMATION_SCHEMA", "SQLITE_MASTER",
        }
        candidates = re.findall(r"\b([A-Z_]{3,})\b", sql_upper)
        for kw in candidates:
            if kw not in already_blocked and len(kw) > 3:
                return kw
        return None

    @staticmethod
    def _apply_kb_entries(entries: list[dict[str, Any]]) -> None:
        if not THREATS_KB.exists():
            logger.warning("threats.json not found at %s", THREATS_KB)
            return
        with open(THREATS_KB, encoding="utf-8") as fh:
            kb: list[dict] = json.load(fh)
        existing_ids = {e["id"] for e in kb}
        added = 0
        for entry in entries:
            if entry["id"] not in existing_ids:
                kb.append(entry)
                added += 1
        if added:
            with open(THREATS_KB, "w", encoding="utf-8") as fh:
                json.dump(kb, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            logger.debug("threats.json: added %d new entries", added)

    @staticmethod
    def _apply_gateway_patterns(patterns: list[tuple[str, str]]) -> None:
        """Append to the module-level _BLOCKED_SQL_PATTERNS so new gateways pick it up."""
        from rage_core.layers import gateway as gw_module
        existing_labels = {lbl for lbl, _ in gw_module._BLOCKED_SQL_PATTERNS}
        for label, pattern_str in patterns:
            if label not in existing_labels:
                compiled = re.compile(pattern_str, re.IGNORECASE)
                gw_module._BLOCKED_SQL_PATTERNS.append((label, compiled))
                logger.debug("Gateway: hot-added block pattern %r", label)
