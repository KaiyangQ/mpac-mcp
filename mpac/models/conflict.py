"""Conflict models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .envelope import Watermark


class ConflictCategory(str, Enum):
    SCOPE_OVERLAP = "scope_overlap"
    CONCURRENT_WRITE = "concurrent_write"
    SEMANTIC_GOAL_CONFLICT = "semantic_goal_conflict"
    ASSUMPTION_CONTRADICTION = "assumption_contradiction"
    POLICY_VIOLATION = "policy_violation"
    AUTHORITY_CONFLICT = "authority_conflict"
    DEPENDENCY_BREAKAGE = "dependency_breakage"
    RESOURCE_CONTENTION = "resource_contention"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DetectionBasisKind(str, Enum):
    RULE = "rule"
    HEURISTIC = "heuristic"
    MODEL_INFERENCE = "model_inference"
    HUMAN_REPORT = "human_report"


class ConflictState(str, Enum):
    OPEN = "OPEN"
    ACKED = "ACKED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    DISMISSED = "DISMISSED"


@dataclass
class DetectionBasis:
    kind: DetectionBasisKind
    rule_id: str | None = None


@dataclass
class Conflict:
    conflict_id: str
    reporter_id: str
    category: ConflictCategory
    severity: Severity
    basis: DetectionBasis
    description: str
    suggested_action: str
    related_intents: list[str] = field(default_factory=list)
    related_ops: list[str] = field(default_factory=list)
    based_on_watermark: Watermark | None = None
    state: ConflictState = ConflictState.OPEN
