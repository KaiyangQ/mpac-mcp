"""Session coordinator for MPAC."""
from dataclasses import dataclass
from datetime import datetime, timezone
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


@dataclass
class Intent:
    """Internal representation of an intent."""
    intent_id: str
    principal_id: str
    objective: str
    scope: Scope
    state_machine: IntentStateMachine


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


class SessionCoordinator:
    """Coordinates MPAC sessions."""

    def __init__(
        self,
        session_id: str,
        security_profile: str = "open",
        compliance_profile: str = "core",
    ):
        """Initialize coordinator."""
        self.session_id = session_id
        self.security_profile = security_profile
        self.compliance_profile = compliance_profile

        # Internal state
        self.participants: Dict[str, Principal] = {}
        self.intents: Dict[str, Intent] = {}
        self.operations: Dict[str, Operation] = {}
        self.conflicts: Dict[str, Conflict] = {}
        self.lamport_clock = LamportClock()

    def process_message(self, envelope_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process incoming message and generate responses.

        Args:
            envelope_dict: Message envelope as dict

        Returns:
            List of response envelope dicts
        """
        envelope = MessageEnvelope.from_dict(envelope_dict)

        # Update lamport clock from received message
        if envelope.watermark and envelope.watermark.kind == "lamport_clock":
            self.lamport_clock.update(int(envelope.watermark.value))

        # Route message by type
        message_type = envelope.message_type
        responses = []

        if message_type == MessageType.HELLO.value:
            responses = self._handle_hello(envelope)
        elif message_type == MessageType.INTENT_ANNOUNCE.value:
            responses = self._handle_intent_announce(envelope)
        elif message_type == MessageType.OP_PROPOSE.value:
            responses = self._handle_op_propose(envelope)
        elif message_type == MessageType.OP_COMMIT.value:
            responses = self._handle_op_commit(envelope)
        elif message_type == MessageType.CONFLICT_REPORT.value:
            responses = self._handle_conflict_report(envelope)
        elif message_type == MessageType.RESOLUTION.value:
            responses = self._handle_resolution(envelope)

        # Convert responses to dicts
        return [r.to_dict() for r in responses]

    def _handle_hello(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle HELLO message."""
        # Register principal
        principal = Principal(
            principal_id=envelope.sender.principal_id,
            principal_type=envelope.sender.principal_type,
            display_name=envelope.payload.get("display_name", ""),
            roles=envelope.payload.get("roles", ["participant"]),
            capabilities=envelope.payload.get("capabilities", []),
        )
        self.participants[principal.principal_id] = principal

        # Send SESSION_INFO response
        response_envelope = MessageEnvelope.create(
            message_type=MessageType.SESSION_INFO.value,
            session_id=self.session_id,
            sender=Sender(
                principal_id="coordinator",
                principal_type="coordinator",
            ),
            payload={
                "security_profile": self.security_profile,
                "compliance_profile": self.compliance_profile,
            },
            watermark=self.lamport_clock.create_watermark(),
        )
        return [response_envelope]

    def _handle_intent_announce(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle INTENT_ANNOUNCE message."""
        intent_id = envelope.payload.get("intent_id")
        objective = envelope.payload.get("objective")
        scope_data = envelope.payload.get("scope")

        # Parse scope
        scope = Scope.from_dict(scope_data) if isinstance(scope_data, dict) else scope_data

        # Create intent state machine
        state_machine = IntentStateMachine()
        state_machine.transition("ACTIVE")

        # Register intent
        intent = Intent(
            intent_id=intent_id,
            principal_id=envelope.sender.principal_id,
            objective=objective,
            scope=scope,
            state_machine=state_machine,
        )
        self.intents[intent_id] = intent

        responses = []

        # Check for scope overlaps with other active intents
        overlapping_intents = self._find_overlapping_intents(intent)
        for other_intent in overlapping_intents:
            # Auto-generate CONFLICT_REPORT
            conflict_id = str(uuid.uuid4())
            conflict = Conflict(
                conflict_id=conflict_id,
                category="scope_overlap",
                severity="medium",
                principal_a=intent.principal_id,
                principal_b=other_intent.principal_id,
                intent_a=intent_id,
                intent_b=other_intent.intent_id,
                state_machine=ConflictStateMachine(),
            )
            self.conflicts[conflict_id] = conflict

            conflict_report = MessageEnvelope.create(
                message_type=MessageType.CONFLICT_REPORT.value,
                session_id=self.session_id,
                sender=Sender(
                    principal_id="coordinator",
                    principal_type="coordinator",
                ),
                payload={
                    "conflict_id": conflict_id,
                    "category": "scope_overlap",
                    "severity": "medium",
                    "principal_a": intent.principal_id,
                    "principal_b": other_intent.principal_id,
                    "intent_a": intent_id,
                    "intent_b": other_intent.intent_id,
                },
                watermark=self.lamport_clock.create_watermark(),
            )
            responses.append(conflict_report)

        return responses

    def _handle_op_propose(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle OP_PROPOSE message."""
        op_id = envelope.payload.get("op_id")
        intent_id = envelope.payload.get("intent_id")
        target = envelope.payload.get("target")
        op_kind = envelope.payload.get("op_kind")

        # Create operation state machine
        state_machine = OperationStateMachine()

        # Register operation
        operation = Operation(
            op_id=op_id,
            intent_id=intent_id,
            principal_id=envelope.sender.principal_id,
            target=target,
            op_kind=op_kind,
            state_machine=state_machine,
        )
        self.operations[op_id] = operation

        return []

    def _handle_op_commit(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle OP_COMMIT message."""
        op_id = envelope.payload.get("op_id")
        state_ref_before = envelope.payload.get("state_ref_before")
        state_ref_after = envelope.payload.get("state_ref_after")

        # Update operation state
        if op_id in self.operations:
            operation = self.operations[op_id]
            operation.state_ref_before = state_ref_before
            operation.state_ref_after = state_ref_after
            operation.state_machine.transition("COMMITTED")

        return []

    def _handle_conflict_report(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle CONFLICT_REPORT message."""
        conflict_id = envelope.payload.get("conflict_id")

        # Register or update conflict
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
            )
            self.conflicts[conflict_id] = conflict

        return []

    def _handle_resolution(self, envelope: MessageEnvelope) -> List[MessageEnvelope]:
        """Handle RESOLUTION message."""
        conflict_id = envelope.payload.get("conflict_id")
        decision = envelope.payload.get("decision")

        # Update conflict state
        if conflict_id in self.conflicts:
            conflict = self.conflicts[conflict_id]
            # Transition through proper states
            if conflict.state_machine.current_state == ConflictState.OPEN:
                conflict.state_machine.transition("ACKED")
            if conflict.state_machine.current_state == ConflictState.ACKED:
                if decision in ["accept", "reject"]:
                    conflict.state_machine.transition("RESOLVED")
                    conflict.state_machine.transition("CLOSED")

        return []

    def _find_overlapping_intents(self, new_intent: Intent) -> List[Intent]:
        """Find intents that overlap with new intent."""
        overlapping = []
        for intent_id, intent in self.intents.items():
            # Skip same intent
            if intent_id == new_intent.intent_id:
                continue

            # Skip non-active intents
            if intent.state_machine.current_state != IntentState.ACTIVE:
                continue

            # Check scope overlap
            if scope_overlap(new_intent.scope, intent.scope):
                overlapping.append(intent)

        return overlapping
