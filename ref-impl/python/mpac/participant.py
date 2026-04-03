"""Participant client for MPAC protocol."""
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import uuid

from .models import Sender, Scope, Watermark, MessageType
from .envelope import MessageEnvelope
from .watermark import LamportClock


class Participant:
    """MPAC protocol participant."""

    def __init__(
        self,
        principal_id: str,
        principal_type: str,
        display_name: str,
        roles: List[str] = None,
        capabilities: List[str] = None,
    ):
        """Initialize participant.

        Args:
            principal_id: Unique identifier for this principal
            principal_type: Type of principal (e.g., "agent", "system")
            display_name: Human-readable name
            roles: List of roles
            capabilities: List of capabilities
        """
        self.principal_id = principal_id
        self.principal_type = principal_type
        self.display_name = display_name
        self.roles = roles or ["participant"]
        self.capabilities = capabilities or []
        self.lamport_clock = LamportClock()

    def hello(self, session_id: str) -> Dict[str, Any]:
        """Send HELLO message to join session.

        Args:
            session_id: Session ID to join

        Returns:
            Message envelope as dict
        """
        envelope = MessageEnvelope.create(
            message_type=MessageType.HELLO.value,
            session_id=session_id,
            sender=Sender(
                principal_id=self.principal_id,
                principal_type=self.principal_type,
            ),
            payload={
                "display_name": self.display_name,
                "roles": self.roles,
                "capabilities": self.capabilities,
            },
            watermark=self.lamport_clock.create_watermark(),
        )
        return envelope.to_dict()

    def announce_intent(
        self,
        session_id: str,
        intent_id: str,
        objective: str,
        scope: Scope,
    ) -> Dict[str, Any]:
        """Announce an intent.

        Args:
            session_id: Session ID
            intent_id: Intent ID
            objective: Objective description
            scope: Scope object (with kind and appropriate fields: resources/entities/task_ids)

        Returns:
            Message envelope as dict
        """
        envelope = MessageEnvelope.create(
            message_type=MessageType.INTENT_ANNOUNCE.value,
            session_id=session_id,
            sender=Sender(
                principal_id=self.principal_id,
                principal_type=self.principal_type,
            ),
            payload={
                "intent_id": intent_id,
                "objective": objective,
                "scope": scope.to_dict(),
            },
            watermark=self.lamport_clock.create_watermark(),
        )
        return envelope.to_dict()

    def propose_op(
        self,
        session_id: str,
        op_id: str,
        intent_id: str,
        target: str,
        op_kind: str,
    ) -> Dict[str, Any]:
        """Propose an operation.

        Args:
            session_id: Session ID
            op_id: Operation ID
            intent_id: Associated intent ID
            target: Target of operation
            op_kind: Type of operation

        Returns:
            Message envelope as dict
        """
        envelope = MessageEnvelope.create(
            message_type=MessageType.OP_PROPOSE.value,
            session_id=session_id,
            sender=Sender(
                principal_id=self.principal_id,
                principal_type=self.principal_type,
            ),
            payload={
                "op_id": op_id,
                "intent_id": intent_id,
                "target": target,
                "op_kind": op_kind,
            },
            watermark=self.lamport_clock.create_watermark(),
        )
        return envelope.to_dict()

    def commit_op(
        self,
        session_id: str,
        op_id: str,
        intent_id: str,
        target: str,
        op_kind: str,
        state_ref_before: Optional[str] = None,
        state_ref_after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Commit an operation.

        Args:
            session_id: Session ID
            op_id: Operation ID
            intent_id: Associated intent ID
            target: Target of operation
            op_kind: Type of operation
            state_ref_before: State reference before operation
            state_ref_after: State reference after operation

        Returns:
            Message envelope as dict
        """
        envelope = MessageEnvelope.create(
            message_type=MessageType.OP_COMMIT.value,
            session_id=session_id,
            sender=Sender(
                principal_id=self.principal_id,
                principal_type=self.principal_type,
            ),
            payload={
                "op_id": op_id,
                "intent_id": intent_id,
                "target": target,
                "op_kind": op_kind,
                "state_ref_before": state_ref_before,
                "state_ref_after": state_ref_after,
            },
            watermark=self.lamport_clock.create_watermark(),
        )
        return envelope.to_dict()

    def report_conflict(
        self,
        session_id: str,
        conflict_id: str,
        category: str,
        severity: str,
        principal_a: str,
        principal_b: str,
        intent_a: str,
        intent_b: str,
    ) -> Dict[str, Any]:
        """Report a conflict.

        Args:
            session_id: Session ID
            conflict_id: Conflict ID
            category: Conflict category
            severity: Severity level
            principal_a: First principal ID
            principal_b: Second principal ID
            intent_a: First intent ID
            intent_b: Second intent ID

        Returns:
            Message envelope as dict
        """
        envelope = MessageEnvelope.create(
            message_type=MessageType.CONFLICT_REPORT.value,
            session_id=session_id,
            sender=Sender(
                principal_id=self.principal_id,
                principal_type=self.principal_type,
            ),
            payload={
                "conflict_id": conflict_id,
                "category": category,
                "severity": severity,
                "principal_a": principal_a,
                "principal_b": principal_b,
                "intent_a": intent_a,
                "intent_b": intent_b,
            },
            watermark=self.lamport_clock.create_watermark(),
        )
        return envelope.to_dict()

    def resolve_conflict(
        self,
        session_id: str,
        conflict_id: str,
        decision: str,
    ) -> Dict[str, Any]:
        """Resolve a conflict.

        Args:
            session_id: Session ID
            conflict_id: Conflict ID
            decision: Resolution decision (approved, rejected, dismissed, etc.)

        Returns:
            Message envelope as dict
        """
        envelope = MessageEnvelope.create(
            message_type=MessageType.RESOLUTION.value,
            session_id=session_id,
            sender=Sender(
                principal_id=self.principal_id,
                principal_type=self.principal_type,
            ),
            payload={
                "conflict_id": conflict_id,
                "decision": decision,
            },
            watermark=self.lamport_clock.create_watermark(),
        )
        return envelope.to_dict()
