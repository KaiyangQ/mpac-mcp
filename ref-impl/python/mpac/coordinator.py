"""Session coordinator for MPAC.

Implements:
- Session management (HELLO / SESSION_INFO)
- Liveness detection via HEARTBEAT / GOODBYE (Section 14)
- Intent lifecycle: ANNOUNCE, UPDATE, WITHDRAW, CLAIM, TTL expiry (Sections 15)
- Operation lifecycle: PROPOSE, COMMIT, REJECT with intent-terminated auto-rejection
- Scope overlap conflict detection
- Conflict workflow: ACK, ESCALATE, RESOLUTION (Section 17-18)
- Intent Expiry Cascade (Section 15.7)
- Conflict Auto-Dismissal on intent termination (Section 17.9)
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import uuid

from .models import (
    Principal,
    Sender,
    Watermark,
    Scope,
    MessageType,
    IntentState,
    OperationState,
    ConflictState,
)
from .envelope import MessageEnvelope
from .watermark import LamportClock
from .scope import scope_overlap
from .state_machines import (
    IntentStateMachine,
    OperationStateMachine,
    ConflictStateMachine,
)


def _now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


# ================================================================
#  Internal data classes
# ================================================================

@dataclass
class Intent:
    """Internal representation of an intent."""
    intent_id: str
    principal_id: str
    objective: str
    scope: Scope
    state_machine: IntentStateMachine
    received_at: datetime = field(default_factory=_now)
    ttl_sec: Optional[float] = None
    expires_at: Optional[datetime] = None
    last_message_id: Optional[str] = None
    claimed_by: Optional[str] = None  # principal_id that claimed this intent


@dataclass
class Operation:
    """Internal representation of an operation."""
    op_id: str
    intent_id: str
    principal_id: str
    target: str
    op_kind: str
    state_machine: OperationStateMachine
    state_ref_before: Optional[str] = None
    state_ref_after: Optional[str] = None
    created_at: datetime = field(default_factory=_now)


@dataclass
class Conflict:
    """Internal representation of a conflict."""
    conflict_id: str
    category: str
    severity: str
    principal_a: str
    principal_b: str
    intent_a: str
    intent_b: str
    state_machine: ConflictStateMachine
    related_intents: List[str] = field(default_factory=list)
    related_ops: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)
    escalated_to: Optional[str] = None
    escalated_at: Optional[datetime] = None


@dataclass
class ParticipantInfo:
    """Liveness tracking for a participant."""
    principal: Principal
    last_seen: datetime = field(default_factory=_now)
    status: str = "idle"  # idle | working | blocked | awaiting_review | offline
    is_available: bool = True


# ================================================================
#  Coordinator
# ================================================================

class SessionCoordinator:
    """Coordinates MPAC sessions."""

    def __init__(
        self,
        session_id: str,
        security_profile: str = "open",
        compliance_profile: str = "core",
        intent_expiry_grace_sec: float = 30.0,
        heartbeat_interval_sec: float = 30.0,
        unavailability_timeout_sec: float = 90.0,
        resolution_timeout_sec: float = 300.0,
    ):
        self.session_id = session_id
        self.security_profile = security_profile
        self.compliance_profile = compliance_profile
        self.intent_expiry_grace_sec = intent_expiry_grace_sec
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.unavailability_timeout_sec = unavailability_timeout_sec
        self.resolution_timeout_sec = resolution_timeout_sec

        # Internal state
        self.participants: Dict[str, ParticipantInfo] = {}
        self.intents: Dict[str, Intent] = {}
        self.operations: Dict[str, Operation] = {}
        self.conflicts: Dict[str, Conflict] = {}
        self.lamport_clock = LamportClock()
        self.claims: Dict[str, str] = {}  # original_intent_id → claim_id

    # ================================================================
    #  Main message processing
    # ================================================================

    def process_message(self, envelope_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process incoming message and generate responses."""
        envelope = MessageEnvelope.from_dict(envelope_dict)

        # Update lamport clock
        if envelope.watermark and envelope.watermark.kind == "lamport_clock":
            self.lamport_clock.update(int(envelope.watermark.value))

        # Update liveness for sender
        pid = envelope.sender.principal_id
        if pid in self.participants:
            self.participants[pid].last_seen = _now()

        # Route message by type
        mt = envelope.message_type
        responses: List[MessageEnvelope] = []

        if mt == MessageType.HELLO.value:
            responses = self._handle_hello(envelope)
        elif mt == MessageType.HEARTBEAT.value:
            responses = self._handle_heartbeat(envelope)
        elif mt == MessageType.GOODBYE.value:
            responses = self._handle_goodbye(envelope)
        elif mt == MessageType.INTENT_ANNOUNCE.value:
            responses = self._handle_intent_announce(envelope)
        elif mt == MessageType.INTENT_UPDATE.value:
            responses = self._handle_intent_update(envelope)
        elif mt == MessageType.INTENT_WITHDRAW.value:
            responses = self._handle_intent_withdraw(envelope)
        elif mt == MessageType.INTENT_CLAIM.value:
            responses = self._handle_intent_claim(envelope)
        elif mt == MessageType.OP_PROPOSE.value:
            responses = self._handle_op_propose(envelope)
        elif mt == MessageType.OP_COMMIT.value:
            responses = self._handle_op_commit(envelope)
        elif mt == MessageType.CONFLICT_REPORT.value:
            responses = self._handle_conflict_report(envelope)
        elif mt == MessageType.CONFLICT_ACK.value:
            responses = self._handle_conflict_ack(envelope)
        elif mt == MessageType.CONFLICT_ESCALATE.value:
            responses = self._handle_conflict_escalate(envelope)
        elif mt == MessageType.RESOLUTION.value:
            responses = self._handle_resolution(envelope)

        return [r.to_dict() for r in responses]

    # ================================================================
    #  Time-based lifecycle checks
    # ================================================================

    def check_expiry(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Check intents for TTL expiry and cascade (Section 15.7 + 17.9)."""
        if now is None:
            now = _now()

        all_responses: List[MessageEnvelope] = []

        for intent in list(self.intents.values()):
            if (
                intent.expires_at is not None
                and not intent.state_machine.is_terminal()
                and intent.state_machine.current_state != IntentState.ANNOUNCED
                and now >= intent.expires_at
            ):
                intent.state_machine.transition("EXPIRED")
                all_responses.extend(
                    self._cascade_intent_termination(intent.intent_id)
                )

        all_responses.extend(self._check_auto_dismiss())
        return [r.to_dict() for r in all_responses]

    def check_liveness(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Detect unavailable participants and cascade (Section 14.5).

        Should be called periodically. When a participant has not sent any
        message for longer than unavailability_timeout_sec:
        - Mark participant unavailable
        - Broadcast PROTOCOL_ERROR (PARTICIPANT_UNAVAILABLE)
        - Suspend their active intents (Section 14.5.2)
        - Abandon their in-flight proposals (Section 14.5.3)
        """
        if now is None:
            now = _now()

        threshold = timedelta(seconds=self.unavailability_timeout_sec)
        all_responses: List[MessageEnvelope] = []

        for pid, info in list(self.participants.items()):
            if not info.is_available:
                continue
            if info.status == "offline":
                continue  # offline status exempt from heartbeat

            if now - info.last_seen > threshold:
                info.is_available = False
                all_responses.extend(self._handle_participant_unavailable(pid))

        return [r.to_dict() for r in all_responses]

    def check_resolution_timeouts(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Auto-escalate conflicts that exceed resolution_timeout_sec (Section 18.6.1).

        Conflicts in OPEN or ACKED state for longer than the timeout are
        auto-escalated. If no arbiter is available, the scope is frozen.
        """
        if now is None:
            now = _now()

        threshold = timedelta(seconds=self.resolution_timeout_sec)
        all_responses: List[MessageEnvelope] = []

        for conflict in list(self.conflicts.values()):
            if conflict.state_machine.current_state not in (
                ConflictState.OPEN, ConflictState.ACKED
            ):
                continue

            if now - conflict.created_at <= threshold:
                continue

            # Find an arbiter
            arbiter_id = self._find_arbiter()

            if arbiter_id:
                # Auto-escalate to arbiter
                try:
                    if conflict.state_machine.current_state == ConflictState.OPEN:
                        conflict.state_machine.transition("ACKED")
                    conflict.state_machine.transition("ESCALATED")
                except ValueError:
                    continue

                conflict.escalated_to = arbiter_id
                conflict.escalated_at = now

                all_responses.append(self._make_envelope(
                    MessageType.CONFLICT_ESCALATE.value,
                    {
                        "conflict_id": conflict.conflict_id,
                        "escalate_to": arbiter_id,
                        "reason": "resolution_timeout",
                        "context": f"Conflict unresolved for >{self.resolution_timeout_sec}s",
                    },
                ))

            else:
                # No arbiter — emit PROTOCOL_ERROR with RESOLUTION_TIMEOUT
                all_responses.append(self._make_envelope(
                    MessageType.PROTOCOL_ERROR.value,
                    {
                        "error_code": "RESOLUTION_TIMEOUT",
                        "refers_to": conflict.conflict_id,
                        "description": f"No arbiter available; conflict {conflict.conflict_id} unresolved for >{self.resolution_timeout_sec}s",
                    },
                ))

        return [r.to_dict() for r in all_responses]

    # ================================================================
    #  Session layer handlers
    # ================================================================

    def _handle_hello(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle HELLO message."""
        principal = Principal(
            principal_id=envelope.sender.principal_id,
            principal_type=envelope.sender.principal_type,
            display_name=envelope.payload.get("display_name", ""),
            roles=envelope.payload.get("roles", ["participant"]),
            capabilities=envelope.payload.get("capabilities", []),
        )
        self.participants[principal.principal_id] = ParticipantInfo(
            principal=principal,
            last_seen=_now(),
            status="idle",
            is_available=True,
        )

        # Check if this is a reconnection — restore suspended intents
        for intent in self.intents.values():
            if (
                intent.principal_id == principal.principal_id
                and intent.state_machine.current_state == IntentState.SUSPENDED
                and intent.claimed_by is None
            ):
                intent.state_machine.transition("ACTIVE")

        return [self._make_envelope(
            MessageType.SESSION_INFO.value,
            {
                "security_profile": self.security_profile,
                "compliance_profile": self.compliance_profile,
            },
        )]

    def _handle_heartbeat(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle HEARTBEAT message (Section 14.4).

        Updates liveness tracking and participant status.
        If the participant was previously marked unavailable, restore them.
        """
        pid = envelope.sender.principal_id
        status = envelope.payload.get("status", "idle")

        if pid in self.participants:
            info = self.participants[pid]
            info.last_seen = _now()
            info.status = status

            # Reconnection: restore availability and suspended intents
            if not info.is_available:
                info.is_available = True
                for intent in self.intents.values():
                    if (
                        intent.principal_id == pid
                        and intent.state_machine.current_state == IntentState.SUSPENDED
                        and intent.claimed_by is None
                    ):
                        intent.state_machine.transition("ACTIVE")

        return []

    def _handle_goodbye(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle GOODBYE message (Section 14.4).

        Processes intent_disposition:
        - withdraw (default): withdraw all active intents
        - expire: let them expire naturally via TTL
        - transfer: offer for adoption (not yet implemented)
        Also abandons in-flight proposals.
        """
        pid = envelope.sender.principal_id
        disposition = envelope.payload.get("intent_disposition", "withdraw")
        active_intent_ids = envelope.payload.get("active_intents", [])

        responses: List[MessageEnvelope] = []

        # Mark participant as unavailable
        if pid in self.participants:
            self.participants[pid].is_available = False
            self.participants[pid].status = "offline"

        # Collect active intents for this participant if not specified
        if not active_intent_ids:
            active_intent_ids = [
                iid for iid, intent in self.intents.items()
                if intent.principal_id == pid
                and not intent.state_machine.is_terminal()
                and intent.state_machine.current_state != IntentState.ANNOUNCED
            ]

        # Apply disposition
        if disposition == "withdraw":
            for iid in active_intent_ids:
                if iid in self.intents:
                    intent = self.intents[iid]
                    try:
                        intent.state_machine.transition("WITHDRAWN")
                        responses.extend(
                            self._cascade_intent_termination(iid)
                        )
                    except ValueError:
                        pass
        elif disposition == "expire":
            pass  # let TTL handle it naturally
        # "transfer" — future work

        # Abandon in-flight proposals from this participant
        for op in self.operations.values():
            if (
                op.principal_id == pid
                and op.state_machine.current_state == OperationState.PROPOSED
            ):
                op.state_machine.transition("ABANDONED")

        # Auto-dismiss any conflicts that are now fully terminal
        responses.extend(self._check_auto_dismiss())

        return responses

    # ================================================================
    #  Intent layer handlers
    # ================================================================

    def _handle_intent_announce(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle INTENT_ANNOUNCE (Section 15.3)."""
        intent_id = envelope.payload.get("intent_id")
        objective = envelope.payload.get("objective")
        scope_data = envelope.payload.get("scope")
        ttl_sec = envelope.payload.get("ttl_sec")

        scope = Scope.from_dict(scope_data) if isinstance(scope_data, dict) else scope_data

        state_machine = IntentStateMachine()
        state_machine.transition("ACTIVE")

        now = _now()
        expires_at = None
        if ttl_sec is not None:
            expires_at = now + timedelta(seconds=float(ttl_sec))

        intent = Intent(
            intent_id=intent_id,
            principal_id=envelope.sender.principal_id,
            objective=objective,
            scope=scope,
            state_machine=state_machine,
            received_at=now,
            ttl_sec=float(ttl_sec) if ttl_sec is not None else None,
            expires_at=expires_at,
            last_message_id=envelope.message_id,
        )
        self.intents[intent_id] = intent

        responses = []

        # Scope overlap detection
        for other in self._find_overlapping_intents(intent):
            conflict_id = str(uuid.uuid4())
            conflict = Conflict(
                conflict_id=conflict_id,
                category="scope_overlap",
                severity="medium",
                principal_a=intent.principal_id,
                principal_b=other.principal_id,
                intent_a=intent_id,
                intent_b=other.intent_id,
                state_machine=ConflictStateMachine(),
                related_intents=[intent_id, other.intent_id],
                related_ops=[],
            )
            self.conflicts[conflict_id] = conflict
            responses.append(self._make_envelope(
                MessageType.CONFLICT_REPORT.value,
                {
                    "conflict_id": conflict_id,
                    "category": "scope_overlap",
                    "severity": "medium",
                    "principal_a": intent.principal_id,
                    "principal_b": other.principal_id,
                    "intent_a": intent_id,
                    "intent_b": other.intent_id,
                },
            ))

        return responses

    def _handle_intent_update(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle INTENT_UPDATE (Section 15.4).

        Can update: objective, scope, ttl_sec.
        If scope changes, re-run overlap detection.
        """
        intent_id = envelope.payload.get("intent_id")
        if intent_id not in self.intents:
            return []

        intent = self.intents[intent_id]

        # Only owning principal can update
        if intent.principal_id != envelope.sender.principal_id:
            return []

        # Must be ACTIVE
        if intent.state_machine.current_state != IntentState.ACTIVE:
            return []

        responses: List[MessageEnvelope] = []
        scope_changed = False

        # Update objective
        if "objective" in envelope.payload:
            intent.objective = envelope.payload["objective"]

        # Update scope
        if "scope" in envelope.payload:
            scope_data = envelope.payload["scope"]
            new_scope = Scope.from_dict(scope_data) if isinstance(scope_data, dict) else scope_data
            intent.scope = new_scope
            scope_changed = True

        # Update TTL
        if "ttl_sec" in envelope.payload:
            ttl_sec = float(envelope.payload["ttl_sec"])
            intent.ttl_sec = ttl_sec
            intent.expires_at = _now() + timedelta(seconds=ttl_sec)

        intent.last_message_id = envelope.message_id

        # Re-check scope overlaps if scope changed
        if scope_changed:
            for other in self._find_overlapping_intents(intent):
                # Check if a conflict already exists for this pair
                already_exists = any(
                    (c.intent_a == intent_id and c.intent_b == other.intent_id)
                    or (c.intent_b == intent_id and c.intent_a == other.intent_id)
                    for c in self.conflicts.values()
                    if not c.state_machine.is_terminal()
                )
                if not already_exists:
                    conflict_id = str(uuid.uuid4())
                    conflict = Conflict(
                        conflict_id=conflict_id,
                        category="scope_overlap",
                        severity="medium",
                        principal_a=intent.principal_id,
                        principal_b=other.principal_id,
                        intent_a=intent_id,
                        intent_b=other.intent_id,
                        state_machine=ConflictStateMachine(),
                        related_intents=[intent_id, other.intent_id],
                        related_ops=[],
                    )
                    self.conflicts[conflict_id] = conflict
                    responses.append(self._make_envelope(
                        MessageType.CONFLICT_REPORT.value,
                        {
                            "conflict_id": conflict_id,
                            "category": "scope_overlap",
                            "severity": "medium",
                            "principal_a": intent.principal_id,
                            "principal_b": other.principal_id,
                            "intent_a": intent_id,
                            "intent_b": other.intent_id,
                        },
                    ))

        return responses

    def _handle_intent_withdraw(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle INTENT_WITHDRAW (Section 15.5)."""
        intent_id = envelope.payload.get("intent_id")

        if intent_id not in self.intents:
            return []

        intent = self.intents[intent_id]

        if intent.principal_id != envelope.sender.principal_id:
            return []

        try:
            intent.state_machine.transition("WITHDRAWN")
        except ValueError:
            return []

        cascade_responses = self._cascade_intent_termination(intent_id)
        dismiss_responses = self._check_auto_dismiss()
        return cascade_responses + dismiss_responses

    def _handle_intent_claim(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle INTENT_CLAIM (Section 14.5.4).

        Allows a participant to claim a suspended intent from an unavailable
        participant, creating a new intent that takes over its scope.
        """
        claim_id = envelope.payload.get("claim_id")
        original_intent_id = envelope.payload.get("original_intent_id")
        new_intent_id = envelope.payload.get("new_intent_id")
        objective = envelope.payload.get("objective")
        scope_data = envelope.payload.get("scope")
        claimer_pid = envelope.sender.principal_id

        if original_intent_id not in self.intents:
            return [self._make_protocol_error(
                "INVALID_REFERENCE",
                envelope.message_id,
                f"Intent {original_intent_id} does not exist",
            )]

        # First-claim-wins: reject if already claimed (check before state)
        if original_intent_id in self.claims:
            return [self._make_protocol_error(
                "CLAIM_CONFLICT",
                envelope.message_id,
                f"Intent {original_intent_id} already claimed by claim {self.claims[original_intent_id]}",
            )]

        original = self.intents[original_intent_id]

        # Must be suspended
        if original.state_machine.current_state != IntentState.SUSPENDED:
            return [self._make_protocol_error(
                "INVALID_REFERENCE",
                envelope.message_id,
                f"Intent {original_intent_id} is not SUSPENDED (state: {original.state_machine.current_state.value})",
            )]

        # Register claim
        self.claims[original_intent_id] = claim_id

        # Mark original as claimed
        original.claimed_by = claimer_pid

        # Transition original intent to SUPERSEDED
        try:
            original.state_machine.transition("WITHDRAWN")
        except ValueError:
            pass

        # Create new intent in ACTIVE state
        scope = Scope.from_dict(scope_data) if isinstance(scope_data, dict) else scope_data
        state_machine = IntentStateMachine()
        state_machine.transition("ACTIVE")

        now = _now()
        new_intent = Intent(
            intent_id=new_intent_id,
            principal_id=claimer_pid,
            objective=objective,
            scope=scope,
            state_machine=state_machine,
            received_at=now,
            last_message_id=envelope.message_id,
        )
        self.intents[new_intent_id] = new_intent

        responses: List[MessageEnvelope] = []

        # Cascade the original intent termination (reject its proposals)
        responses.extend(self._cascade_intent_termination(original_intent_id))

        # Check scope overlaps for new intent
        for other in self._find_overlapping_intents(new_intent):
            conflict_id = str(uuid.uuid4())
            conflict = Conflict(
                conflict_id=conflict_id,
                category="scope_overlap",
                severity="medium",
                principal_a=new_intent.principal_id,
                principal_b=other.principal_id,
                intent_a=new_intent_id,
                intent_b=other.intent_id,
                state_machine=ConflictStateMachine(),
                related_intents=[new_intent_id, other.intent_id],
                related_ops=[],
            )
            self.conflicts[conflict_id] = conflict
            responses.append(self._make_envelope(
                MessageType.CONFLICT_REPORT.value,
                {
                    "conflict_id": conflict_id,
                    "category": "scope_overlap",
                    "severity": "medium",
                    "principal_a": new_intent.principal_id,
                    "principal_b": other.principal_id,
                    "intent_a": new_intent_id,
                    "intent_b": other.intent_id,
                },
            ))

        return responses

    # ================================================================
    #  Operation layer handlers
    # ================================================================

    def _handle_op_propose(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle OP_PROPOSE (Section 16.1)."""
        op_id = envelope.payload.get("op_id")
        intent_id = envelope.payload.get("intent_id")
        target = envelope.payload.get("target")
        op_kind = envelope.payload.get("op_kind")

        state_machine = OperationStateMachine()
        operation = Operation(
            op_id=op_id,
            intent_id=intent_id,
            principal_id=envelope.sender.principal_id,
            target=target,
            op_kind=op_kind,
            state_machine=state_machine,
        )
        self.operations[op_id] = operation

        # Track operation in related conflicts
        for conflict in self.conflicts.values():
            if intent_id in (conflict.intent_a, conflict.intent_b):
                if op_id not in conflict.related_ops:
                    conflict.related_ops.append(op_id)

        responses = []

        if intent_id in self.intents:
            intent = self.intents[intent_id]
            if intent.state_machine.is_terminal():
                state_machine.transition("REJECTED")
                responses.append(self._make_op_reject(
                    op_id, "intent_terminated", intent.last_message_id,
                ))
            elif intent.state_machine.current_state == IntentState.SUSPENDED:
                state_machine.transition("FROZEN")

        return responses

    def _handle_op_commit(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle OP_COMMIT (Section 16.2)."""
        op_id = envelope.payload.get("op_id")
        intent_id = envelope.payload.get("intent_id")
        state_ref_before = envelope.payload.get("state_ref_before")
        state_ref_after = envelope.payload.get("state_ref_after")

        if op_id in self.operations:
            operation = self.operations[op_id]
            operation.state_ref_before = state_ref_before
            operation.state_ref_after = state_ref_after
            operation.state_machine.transition("COMMITTED")
        else:
            state_machine = OperationStateMachine()
            operation = Operation(
                op_id=op_id,
                intent_id=intent_id or "",
                principal_id=envelope.sender.principal_id,
                target=envelope.payload.get("target", ""),
                op_kind=envelope.payload.get("op_kind", ""),
                state_machine=state_machine,
                state_ref_before=state_ref_before,
                state_ref_after=state_ref_after,
            )
            state_machine.transition("COMMITTED")
            self.operations[op_id] = operation

            if intent_id:
                for conflict in self.conflicts.values():
                    if intent_id in (conflict.intent_a, conflict.intent_b):
                        if op_id not in conflict.related_ops:
                            conflict.related_ops.append(op_id)

        return []

    # ================================================================
    #  Conflict layer handlers
    # ================================================================

    def _handle_conflict_report(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle CONFLICT_REPORT."""
        conflict_id = envelope.payload.get("conflict_id")

        if conflict_id not in self.conflicts:
            conflict = Conflict(
                conflict_id=conflict_id,
                category=envelope.payload.get("category", "unknown"),
                severity=envelope.payload.get("severity", "medium"),
                principal_a=envelope.payload.get("principal_a", ""),
                principal_b=envelope.payload.get("principal_b", ""),
                intent_a=envelope.payload.get("intent_a", ""),
                intent_b=envelope.payload.get("intent_b", ""),
                state_machine=ConflictStateMachine(),
                related_intents=[
                    x for x in [
                        envelope.payload.get("intent_a"),
                        envelope.payload.get("intent_b"),
                    ] if x
                ],
            )
            self.conflicts[conflict_id] = conflict

        return []

    def _handle_conflict_ack(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle CONFLICT_ACK (Section 17.3).

        Transitions conflict from OPEN → ACKED.
        """
        conflict_id = envelope.payload.get("conflict_id")

        if conflict_id not in self.conflicts:
            return []

        conflict = self.conflicts[conflict_id]

        if conflict.state_machine.current_state == ConflictState.OPEN:
            conflict.state_machine.transition("ACKED")

        return []

    def _handle_conflict_escalate(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle CONFLICT_ESCALATE (Section 17.5).

        Transitions conflict to ESCALATED and records escalation target.
        """
        conflict_id = envelope.payload.get("conflict_id")
        escalate_to = envelope.payload.get("escalate_to")

        if conflict_id not in self.conflicts:
            return []

        conflict = self.conflicts[conflict_id]

        try:
            if conflict.state_machine.current_state == ConflictState.OPEN:
                conflict.state_machine.transition("ACKED")
            if conflict.state_machine.current_state == ConflictState.ACKED:
                conflict.state_machine.transition("ESCALATED")
        except ValueError:
            return []

        conflict.escalated_to = escalate_to
        conflict.escalated_at = _now()

        return []

    def _handle_resolution(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle RESOLUTION (Section 17.7)."""
        conflict_id = envelope.payload.get("conflict_id")
        decision = envelope.payload.get("decision")

        if conflict_id not in self.conflicts:
            return []

        conflict = self.conflicts[conflict_id]

        # Handle from any non-terminal state
        if conflict.state_machine.is_terminal():
            return []

        if decision == "dismissed":
            # Direct dismiss from any open state
            state = conflict.state_machine.current_state
            if state == ConflictState.OPEN:
                conflict.state_machine.transition("DISMISSED")
            elif state == ConflictState.ACKED:
                conflict.state_machine.transition("DISMISSED")
            elif state == ConflictState.ESCALATED:
                conflict.state_machine.transition("DISMISSED")
        else:
            # Resolve → Close
            state = conflict.state_machine.current_state
            if state == ConflictState.OPEN:
                conflict.state_machine.transition("ACKED")
            if conflict.state_machine.current_state == ConflictState.ACKED:
                conflict.state_machine.transition("RESOLVED")
                conflict.state_machine.transition("CLOSED")
            elif conflict.state_machine.current_state == ConflictState.ESCALATED:
                conflict.state_machine.transition("RESOLVED")
                conflict.state_machine.transition("CLOSED")

        return []

    # ================================================================
    #  Intent Expiry Cascade (Section 15.7)
    # ================================================================

    def _cascade_intent_termination(self, intent_id: str) -> List[MessageEnvelope]:
        """Cascade intent termination to dependent operations."""
        intent = self.intents.get(intent_id)
        if intent is None:
            return []

        responses: List[MessageEnvelope] = []

        for operation in list(self.operations.values()):
            if operation.intent_id != intent_id:
                continue

            current = operation.state_machine.current_state
            if current == OperationState.PROPOSED:
                operation.state_machine.transition("REJECTED")
                responses.append(self._make_op_reject(
                    operation.op_id, "intent_terminated", intent.last_message_id,
                ))
            elif current == OperationState.FROZEN:
                operation.state_machine.transition("REJECTED")
                responses.append(self._make_op_reject(
                    operation.op_id, "intent_terminated", intent.last_message_id,
                ))

        return responses

    # ================================================================
    #  Conflict Auto-Dismissal (Section 17.9)
    # ================================================================

    def _check_auto_dismiss(self) -> List[MessageEnvelope]:
        """Auto-dismiss conflicts where all related entities are terminal."""
        responses: List[MessageEnvelope] = []

        for conflict in list(self.conflicts.values()):
            if conflict.state_machine.is_terminal():
                continue

            all_intents_terminal = all(
                self.intents.get(iid) is None or self.intents[iid].state_machine.is_terminal()
                for iid in conflict.related_intents
            )
            if not all_intents_terminal:
                continue

            has_committed = False
            all_ops_terminal = True
            for oid in conflict.related_ops:
                op = self.operations.get(oid)
                if op is None:
                    continue
                if op.state_machine.current_state == OperationState.COMMITTED:
                    has_committed = True
                    break
                if not op.state_machine.is_terminal():
                    all_ops_terminal = False
                    break

            if has_committed or not all_ops_terminal:
                continue

            try:
                conflict.state_machine.transition("DISMISSED")
            except ValueError:
                continue

            responses.append(self._make_envelope(
                MessageType.RESOLUTION.value,
                {
                    "conflict_id": conflict.conflict_id,
                    "decision": "dismissed",
                    "rationale": "all_related_entities_terminated",
                },
            ))

        return responses

    # ================================================================
    #  Liveness cascade
    # ================================================================

    def _handle_participant_unavailable(self, principal_id: str) -> List[MessageEnvelope]:
        """Handle a participant becoming unavailable (Section 14.5).

        - Broadcast PROTOCOL_ERROR(PARTICIPANT_UNAVAILABLE)
        - Suspend their active intents
        - Abandon their in-flight proposals
        """
        responses: List[MessageEnvelope] = []

        # Broadcast unavailability
        responses.append(self._make_envelope(
            MessageType.PROTOCOL_ERROR.value,
            {
                "error_code": "PARTICIPANT_UNAVAILABLE",
                "refers_to": principal_id,
                "description": f"Participant {principal_id} is unavailable (no heartbeat for >{self.unavailability_timeout_sec}s)",
            },
        ))

        # Suspend active intents (Section 14.5.2)
        for intent in self.intents.values():
            if (
                intent.principal_id == principal_id
                and intent.state_machine.current_state == IntentState.ACTIVE
            ):
                intent.state_machine.transition("SUSPENDED")

                # Freeze any PROPOSED operations referencing this intent
                for op in self.operations.values():
                    if (
                        op.intent_id == intent.intent_id
                        and op.state_machine.current_state == OperationState.PROPOSED
                    ):
                        op.state_machine.transition("FROZEN")

        # Abandon orphaned proposals from this participant (Section 14.5.3)
        for op in self.operations.values():
            if op.principal_id != principal_id:
                continue
            if op.state_machine.current_state == OperationState.PROPOSED:
                op.state_machine.transition("ABANDONED")
            elif op.state_machine.current_state == OperationState.FROZEN:
                op.state_machine.transition("ABANDONED")

        return responses

    # ================================================================
    #  Helpers
    # ================================================================

    def _make_envelope(self, message_type: str, payload: Dict[str, Any]) -> MessageEnvelope:
        """Create a coordinator-originated envelope."""
        return MessageEnvelope.create(
            message_type=message_type,
            session_id=self.session_id,
            sender=Sender(principal_id="coordinator", principal_type="coordinator"),
            payload=payload,
            watermark=self.lamport_clock.create_watermark(),
        )

    def _make_op_reject(self, op_id: str, reason: str, refers_to: Optional[str] = None) -> MessageEnvelope:
        """Create OP_REJECT envelope."""
        payload: Dict[str, Any] = {"op_id": op_id, "reason": reason}
        if refers_to:
            payload["refers_to"] = refers_to
        return self._make_envelope(MessageType.OP_REJECT.value, payload)

    def _make_protocol_error(self, error_code: str, refers_to: Optional[str], description: str) -> MessageEnvelope:
        """Create PROTOCOL_ERROR envelope."""
        payload: Dict[str, Any] = {
            "error_code": error_code,
            "description": description,
        }
        if refers_to:
            payload["refers_to"] = refers_to
        return self._make_envelope(MessageType.PROTOCOL_ERROR.value, payload)

    def _find_overlapping_intents(self, new_intent: Intent) -> List[Intent]:
        """Find active intents that overlap with new intent."""
        overlapping = []
        for intent_id, intent in self.intents.items():
            if intent_id == new_intent.intent_id:
                continue
            # ACTIVE and SUSPENDED scopes are considered occupied
            if intent.state_machine.current_state not in (IntentState.ACTIVE, IntentState.SUSPENDED):
                continue
            if scope_overlap(new_intent.scope, intent.scope):
                overlapping.append(intent)
        return overlapping

    def _find_arbiter(self) -> Optional[str]:
        """Find an available arbiter principal."""
        for pid, info in self.participants.items():
            if not info.is_available:
                continue
            if "arbiter" in info.principal.roles:
                return pid
        return None
