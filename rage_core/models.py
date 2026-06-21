"""
Core data models for the RAGE multi-turn defense system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Band(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


class ActionStatus(str, Enum):
    PERMITTED = "permitted"
    BLOCKED = "blocked"


@dataclass
class Layer1Signal:
    """Output of the deterministic pre-filter (Layer 1)."""
    matched: bool
    pattern_id: Optional[str] = None
    matched_text: Optional[str] = None


@dataclass
class Layer2Signal:
    """Output of the RAG threat KB (Layer 2)."""
    score: float  # 0.0 – 1.0 cosine similarity to nearest known attack
    top_match_id: Optional[str] = None
    top_match_category: Optional[str] = None
    top_match_technique: Optional[str] = None
    owasp_id: Optional[str] = None
    severity: Optional[str] = None


@dataclass
class Layer3Signal:
    """Output of the dynamic semantic filter with state (Layer 3)."""
    drift: float           # 0.0 – 1.0  (cosine distance from previous turn embedding)
    suspicious: bool       # drift > threshold
    llm_flagged: bool      # LLM judge result (only populated when suspicious=True)
    intent_summary: str = ""   # mini-summary of current turn (untrusted — sanitized)
    # Crescendo-hardening: drift measured against turn-0 (baseline) embedding.
    # While turn-to-turn drift captures abrupt jumps, cumulative_drift detects
    # the slow topic migration that characterises Crescendo-style attacks.
    cumulative_drift: float = 0.0  # cosine distance from conversation-start embedding


@dataclass
class TurnSignal:
    """Aggregated signal for a single conversation turn (all layers combined)."""
    turn_index: int
    text: str
    layer1: Layer1Signal
    layer2: Layer2Signal
    layer3: Layer3Signal
    score: float       # 0 – 100 fused score
    band: Band
    latency_ms: float


@dataclass
class ConversationState:
    """Mutable state threaded through a multi-turn conversation."""
    turn_index: int = 0
    # Embeddings are stored as lists of floats for JSON-serializability
    turn_embeddings: list[list[float]] = field(default_factory=list)
    # Intent summaries per turn (treated as untrusted input)
    intent_summaries: list[str] = field(default_factory=list)
    signals: list[TurnSignal] = field(default_factory=list)
    # Ground-truth vulnerability scores 0-5 (set by the evaluator, not by the defense)
    gt_scores: list[int] = field(default_factory=list)
    # --- Crescendo-hardening: session-level risk tracking ---
    # Exponentially-weighted moving average of per-turn scores (0–1).
    # A series of moderate-risk turns accumulates here and can trigger band elevation
    # even when no single turn crosses the block threshold on its own.
    session_risk_score: float = 0.0
    # Number of consecutive turns that landed in the WARN band.
    # When this reaches the ratchet threshold the pipeline auto-elevates to BLOCK.
    consecutive_warns: int = 0
    # True once any prior turn received WARN or BLOCK (used by ActionGateway export gate).
    had_warn_or_block: bool = False


@dataclass
class GatewaySessionContext:
    """Session signals passed to ActionGateway for context-aware tool gating."""
    session_risk_score: float = 0.0
    had_warn_or_block: bool = False


@dataclass
class DefenseDecision:
    """Final decision returned to the caller."""
    turn_signal: TurnSignal
    action: Band
    reason: str


@dataclass
class ToolCallRequest:
    """Represents a tool-call the agent wants to execute."""
    tool_name: str
    arguments: dict[str, object]


@dataclass
class GatewayVerdict:
    """Result of the action gateway for a tool call."""
    status: ActionStatus
    tool_call: ToolCallRequest
    reason: str


@dataclass
class AUCResult:
    """Result of computing the AUC-of-degradation metric."""
    label: str               # e.g. "without defense" or "with defense"
    turns: list[int]
    gt_scores: list[int]     # Ground-truth vulnerability scores per turn (0–5)
    auc_raw: float           # numpy.trapz result (unnormalized)
    auc_normalized: float    # auc_raw / (5 * n_turns)  →  0 – 1
    compromise_turn: Optional[int]  # first turn where gt_score >= 4, or None
