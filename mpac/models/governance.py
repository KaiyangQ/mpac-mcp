"""Governance policy and resolution models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .conflict import Severity


class GovernanceMode(str, Enum):
    OPEN_COMMIT = "open_commit"
    REVIEW_REQUIRED = "review_required"


class Decision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    DISMISSED = "dismissed"
    HUMAN_OVERRIDE = "human_override"
    POLICY_OVERRIDE = "policy_override"
    MERGED = "merged"
    DEFERRED = "deferred"


@dataclass
class Outcome:
    accepted: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    merged: list[str] = field(default_factory=list)


@dataclass
class Resolution:
    resolution_id: str
    conflict_id: str
    decision: Decision
    outcome: Outcome
    rationale: str = ""
    resolver_id: str = ""


@dataclass
class GovernancePolicy:
    mode: GovernanceMode = GovernanceMode.OPEN_COMMIT
    auto_resolve_low_severity: bool = True
    escalation_threshold: Severity = Severity.HIGH
