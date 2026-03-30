"""Typed MPAC message payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .conflict import DetectionBasis
from .envelope import Watermark
from .governance import Decision, Outcome
from .intent import Scope


@dataclass
class HelloPayload:
    display_name: str
    roles: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    implementation: dict[str, Any] = field(default_factory=dict)


@dataclass
class HeartbeatPayload:
    status: str
    active_intent_id: str | None = None
    summary: str | None = None


@dataclass
class GoodbyePayload:
    reason: str
    active_intents: list[str] = field(default_factory=list)
    intent_disposition: str = "withdraw"


@dataclass
class IntentAnnouncePayload:
    intent_id: str
    objective: str
    scope: Scope
    assumptions: list[str] = field(default_factory=list)
    priority: str = "normal"
    ttl_sec: int = 300


@dataclass
class IntentUpdatePayload:
    intent_id: str
    objective: str | None = None
    scope: Scope | None = None
    assumptions: list[str] | None = None
    ttl_sec: int | None = None


@dataclass
class IntentWithdrawPayload:
    intent_id: str
    reason: str


@dataclass
class OperationPayload:
    op_id: str
    target: str
    op_kind: str
    intent_id: str | None = None
    state_ref_before: str | None = None
    state_ref_after: str | None = None
    change_ref: str | None = None
    summary: str = ""


@dataclass
class OperationRejectPayload:
    op_id: str
    reason: str


@dataclass
class OperationSupersedePayload:
    op_id: str
    supersedes_op_id: str
    intent_id: str | None = None
    target: str = ""
    reason: str = ""


@dataclass
class ConflictReportPayload:
    conflict_id: str
    related_intents: list[str]
    related_ops: list[str]
    category: str
    severity: str
    basis: DetectionBasis
    description: str
    suggested_action: str
    based_on_watermark: Watermark | None = None


@dataclass
class ConflictAckPayload:
    conflict_id: str
    ack_type: str


@dataclass
class ConflictEscalatePayload:
    conflict_id: str
    escalate_to: str
    reason: str
    context: str


@dataclass
class ResolutionPayload:
    resolution_id: str
    conflict_id: str
    decision: Decision
    outcome: Outcome
    rationale: str = ""


@dataclass
class ProtocolErrorPayload:
    error_code: str
    refers_to: str | None
    description: str
