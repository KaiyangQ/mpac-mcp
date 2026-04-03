"""Data models for MPAC protocol."""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import uuid


# ============================================================================
# Enums
# ============================================================================

class MessageType(Enum):
    """MPAC message types."""
    HELLO = "HELLO"
    SESSION_INFO = "SESSION_INFO"
    HEARTBEAT = "HEARTBEAT"
    GOODBYE = "GOODBYE"
    INTENT_ANNOUNCE = "INTENT_ANNOUNCE"
    INTENT_UPDATE = "INTENT_UPDATE"
    INTENT_WITHDRAW = "INTENT_WITHDRAW"
    INTENT_CLAIM = "INTENT_CLAIM"
    OP_PROPOSE = "OP_PROPOSE"
    OP_COMMIT = "OP_COMMIT"
    OP_REJECT = "OP_REJECT"
    OP_SUPERSEDE = "OP_SUPERSEDE"
    CONFLICT_REPORT = "CONFLICT_REPORT"
    CONFLICT_ACK = "CONFLICT_ACK"
    CONFLICT_ESCALATE = "CONFLICT_ESCALATE"
    RESOLUTION = "RESOLUTION"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"


class IntentState(Enum):
    """Intent lifecycle states."""
    ANNOUNCED = "ANNOUNCED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    WITHDRAWN = "WITHDRAWN"
    SUPERSEDED = "SUPERSEDED"
    SUSPENDED = "SUSPENDED"


class OperationState(Enum):
    """Operation lifecycle states."""
    PROPOSED = "PROPOSED"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    ABANDONED = "ABANDONED"
    FROZEN = "FROZEN"


class ConflictState(Enum):
    """Conflict lifecycle states."""
    OPEN = "OPEN"
    ACKED = "ACKED"
    ESCALATED = "ESCALATED"
    DISMISSED = "DISMISSED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class ScopeKind(Enum):
    """Types of scope elements."""
    FILE_SET = "file_set"
    ENTITY_SET = "entity_set"
    TASK_SET = "task_set"


class SecurityProfile(Enum):
    """Security profile levels."""
    OPEN = "open"
    AUTHENTICATED = "authenticated"
    VERIFIED = "verified"


class ComplianceProfile(Enum):
    """Compliance profile levels."""
    CORE = "core"
    GOVERNANCE = "governance"
    SEMANTIC = "semantic"


class Role(Enum):
    """Principal roles."""
    OBSERVER = "observer"
    CONTRIBUTOR = "contributor"
    REVIEWER = "reviewer"
    OWNER = "owner"
    ARBITER = "arbiter"


class ConflictCategory(Enum):
    """Conflict categories."""
    SCOPE_OVERLAP = "scope_overlap"
    CONCURRENT_WRITE = "concurrent_write"
    SEMANTIC_GOAL_CONFLICT = "semantic_goal_conflict"
    ASSUMPTION_CONTRADICTION = "assumption_contradiction"
    POLICY_VIOLATION = "policy_violation"
    AUTHORITY_CONFLICT = "authority_conflict"
    DEPENDENCY_BREAKAGE = "dependency_breakage"
    RESOURCE_CONTENTION = "resource_contention"


class Severity(Enum):
    """Severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Decision(Enum):
    """Resolution decisions."""
    APPROVED = "approved"
    REJECTED = "rejected"
    DISMISSED = "dismissed"
    HUMAN_OVERRIDE = "human_override"
    POLICY_OVERRIDE = "policy_override"
    MERGED = "merged"
    DEFERRED = "deferred"


class HeartbeatStatus(Enum):
    """Participant heartbeat status."""
    IDLE = "idle"
    WORKING = "working"
    BLOCKED = "blocked"
    AWAITING_REVIEW = "awaiting_review"
    OFFLINE = "offline"


class IntentDisposition(Enum):
    """What happens to active intents when a participant leaves."""
    WITHDRAW = "withdraw"
    TRANSFER = "transfer"
    EXPIRE = "expire"


class ErrorCode(Enum):
    """Error codes."""
    MALFORMED_MESSAGE = "MALFORMED_MESSAGE"
    UNKNOWN_MESSAGE_TYPE = "UNKNOWN_MESSAGE_TYPE"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    PARTICIPANT_UNAVAILABLE = "PARTICIPANT_UNAVAILABLE"
    RESOLUTION_TIMEOUT = "RESOLUTION_TIMEOUT"
    SCOPE_FROZEN = "SCOPE_FROZEN"
    CLAIM_CONFLICT = "CLAIM_CONFLICT"


# ============================================================================
# Core Data Models
# ============================================================================

@dataclass
class Principal:
    """Represents a principal in the protocol."""
    principal_id: str
    principal_type: str
    display_name: str
    roles: List[str] = field(default_factory=lambda: ["participant"])
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Principal":
        """Create from dict."""
        return cls(**data)


@dataclass
class Sender:
    """Message sender information."""
    principal_id: str
    principal_type: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Sender":
        """Create from dict."""
        return cls(**data)


@dataclass
class Watermark:
    """Causal context watermark."""
    kind: str = "lamport_clock"  # lamport_clock | vector_clock | causal_frontier | opaque
    value: Any = 0  # kind=lamport_clock → int
    lamport_value: Optional[int] = None  # fallback when kind != lamport_clock

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        d = {"kind": self.kind, "value": self.value}
        if self.lamport_value is not None:
            d["lamport_value"] = self.lamport_value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Watermark":
        """Create from dict."""
        return cls(
            kind=data.get("kind", "lamport_clock"),
            value=data.get("value", 0),
            lamport_value=data.get("lamport_value"),
        )


@dataclass
class Scope:
    """Scope of an intent or operation."""
    kind: str  # file_set | entity_set | task_set | resource_path | query | custom
    resources: Optional[List[str]] = None  # for file_set
    entities: Optional[List[str]] = None   # for entity_set
    task_ids: Optional[List[str]] = None   # for task_set
    pattern: Optional[str] = None          # for resource_path
    canonical_uris: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        d = {"kind": self.kind}
        if self.resources is not None:
            d["resources"] = self.resources
        if self.entities is not None:
            d["entities"] = self.entities
        if self.task_ids is not None:
            d["task_ids"] = self.task_ids
        if self.pattern is not None:
            d["pattern"] = self.pattern
        if self.canonical_uris is not None:
            d["canonical_uris"] = self.canonical_uris
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scope":
        """Create from dict."""
        return cls(
            kind=data["kind"],
            resources=data.get("resources"),
            entities=data.get("entities"),
            task_ids=data.get("task_ids"),
            pattern=data.get("pattern"),
            canonical_uris=data.get("canonical_uris"),
        )


@dataclass
class Basis:
    """How a conflict was detected."""
    kind: str  # rule | heuristic | model_inference | semantic_match | human_report
    rule_id: Optional[str] = None
    matcher: Optional[str] = None
    match_type: Optional[str] = None  # contradictory | equivalent | uncertain
    confidence: Optional[float] = None
    explanation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        d = {"kind": self.kind}
        if self.rule_id is not None:
            d["rule_id"] = self.rule_id
        if self.matcher is not None:
            d["matcher"] = self.matcher
        if self.match_type is not None:
            d["match_type"] = self.match_type
        if self.confidence is not None:
            d["confidence"] = self.confidence
        if self.explanation is not None:
            d["explanation"] = self.explanation
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Basis":
        """Create from dict."""
        return cls(
            kind=data["kind"],
            rule_id=data.get("rule_id"),
            matcher=data.get("matcher"),
            match_type=data.get("match_type"),
            confidence=data.get("confidence"),
            explanation=data.get("explanation"),
        )


@dataclass
class Outcome:
    """Structured resolution result."""
    accepted: Optional[List[str]] = None
    rejected: Optional[List[str]] = None
    merged: Optional[List[str]] = None
    rollback: Optional[str] = None  # MUST when rejected contains COMMITTED ops

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        d = {}
        if self.accepted is not None:
            d["accepted"] = self.accepted
        if self.rejected is not None:
            d["rejected"] = self.rejected
        if self.merged is not None:
            d["merged"] = self.merged
        if self.rollback is not None:
            d["rollback"] = self.rollback
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Outcome":
        """Create from dict."""
        return cls(
            accepted=data.get("accepted"),
            rejected=data.get("rejected"),
            merged=data.get("merged"),
            rollback=data.get("rollback"),
        )


@dataclass
class GovernancePolicy:
    """Governance policy configuration."""
    max_active_intents_per_principal: int = 10
    max_concurrent_operations_per_intent: int = 5
    require_acknowledgment: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GovernancePolicy":
        """Create from dict."""
        return cls(**data)


@dataclass
class LivenessPolicy:
    """Liveness policy configuration (Section 14.3)."""
    heartbeat_interval_sec: int = 30
    unavailability_timeout_sec: int = 90
    orphaned_intent_action: str = "suspend"   # suspend | withdraw
    orphaned_proposal_action: str = "abandon"  # abandon | reject
    intent_claim_approval: str = "auto"  # auto | governance
    intent_claim_grace_period_sec: int = 30
    resolution_timeout_sec: int = 300  # Section 18.6.1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LivenessPolicy":
        """Create from dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Session:
    """Session configuration."""
    session_id: str
    security_profile: str = "open"
    compliance_profile: str = "core"
    governance_policy: Optional[GovernancePolicy] = None
    liveness_policy: Optional[LivenessPolicy] = None

    def __post_init__(self):
        """Initialize policies if not set."""
        if self.governance_policy is None:
            self.governance_policy = GovernancePolicy()
        if self.liveness_policy is None:
            self.liveness_policy = LivenessPolicy()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        data = asdict(self)
        if self.governance_policy:
            data['governance_policy'] = self.governance_policy.to_dict()
        if self.liveness_policy:
            data['liveness_policy'] = self.liveness_policy.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create from dict."""
        data_copy = data.copy()
        if 'governance_policy' in data_copy and isinstance(data_copy['governance_policy'], dict):
            data_copy['governance_policy'] = GovernancePolicy.from_dict(data_copy['governance_policy'])
        if 'liveness_policy' in data_copy and isinstance(data_copy['liveness_policy'], dict):
            data_copy['liveness_policy'] = LivenessPolicy.from_dict(data_copy['liveness_policy'])
        return cls(**data_copy)
