"""Top-level MPAC reference runtime."""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from mpac.models import (
    Conflict,
    ConflictAckPayload,
    ConflictCategory,
    ConflictEscalatePayload,
    ConflictReportPayload,
    ConflictState,
    Decision,
    DetectionBasisKind,
    Envelope,
    GoodbyePayload,
    HeartbeatPayload,
    HelloPayload,
    Intent,
    IntentAnnouncePayload,
    IntentState,
    IntentUpdatePayload,
    IntentWithdrawPayload,
    MessageType,
    Operation,
    OperationPayload,
    OperationRejectPayload,
    OperationState,
    OperationSupersedePayload,
    Outcome,
    ParticipantPresence,
    PresenceStatus,
    Principal,
    PrincipalType,
    ProtocolErrorPayload,
    Resolution,
    ResolutionPayload,
    Role,
    SenderRef,
    Severity,
    Watermark,
)
from mpac.runtime.bus import MessageBus
from mpac.runtime.conflict_detector import ConflictDetector
from mpac.runtime.governor import GovernanceEngine
from mpac.runtime.session import SessionState


class MPACRuntime:
    """A single-process, in-memory MPAC reference runtime."""

    def __init__(self, session_id: str | None = None, *, auto_detect_conflicts: bool = True) -> None:
        self.session = SessionState(session_id=session_id or f"sess-{uuid.uuid4().hex[:8]}")
        self.bus = MessageBus()
        self.detector = ConflictDetector()
        self.governor = GovernanceEngine()
        self.auto_detect_conflicts = auto_detect_conflicts

    def register_agent(self, agent: Any) -> None:
        self.bus.register(agent)

    def receive(self, message: Envelope) -> list[Envelope]:
        queue: deque[Envelope] = deque([message])
        processed: list[Envelope] = []

        while queue:
            current = queue.popleft()
            responses = self._process(current)
            processed.append(current)
            queue.extend(responses)
            queue.extend(self.bus.broadcast(current, self.session))
        return processed

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session.session_id,
            "clock": self.session.lamport_clock,
            "participants": {key: value.to_dict() for key, value in self.session.participants.items()},
            "intents": {key: self._serialize(value) for key, value in self.session.intents.items()},
            "operations": {key: self._serialize(value) for key, value in self.session.operations.items()},
            "conflicts": {key: self._serialize(value) for key, value in self.session.conflicts.items()},
            "resolutions": {key: self._serialize(value) for key, value in self.session.resolutions.items()},
            "shared_state": dict(self.session.shared_state),
            "message_log": list(self.session.message_log),
        }

    def make_envelope(
        self,
        *,
        message_type: MessageType,
        sender_id: str,
        sender_type: PrincipalType,
        payload: Any,
        in_reply_to: str | None = None,
    ) -> Envelope:
        return Envelope(
            message_type=message_type,
            session_id=self.session.session_id,
            sender=SenderRef(principal_id=sender_id, principal_type=sender_type),
            payload=payload,
            in_reply_to=in_reply_to,
        )

    def _process(self, message: Envelope) -> list[Envelope]:
        self.session.tick()
        message.watermark = message.watermark or Watermark(kind="lamport_clock", value=self.session.lamport_clock)
        self._audit(message)
        self._expire_intents()
        error = self._validate_message(message)
        if error:
            self._audit(error)
            return []

        handler = {
            MessageType.HELLO: self._handle_hello,
            MessageType.HEARTBEAT: self._handle_heartbeat,
            MessageType.GOODBYE: self._handle_goodbye,
            MessageType.INTENT_ANNOUNCE: self._handle_intent_announce,
            MessageType.INTENT_UPDATE: self._handle_intent_update,
            MessageType.INTENT_WITHDRAW: self._handle_intent_withdraw,
            MessageType.OP_PROPOSE: self._handle_op_propose,
            MessageType.OP_COMMIT: self._handle_op_commit,
            MessageType.OP_REJECT: self._handle_op_reject,
            MessageType.OP_SUPERSEDE: self._handle_op_supersede,
            MessageType.CONFLICT_REPORT: self._handle_conflict_report,
            MessageType.CONFLICT_ACK: self._handle_conflict_ack,
            MessageType.CONFLICT_ESCALATE: self._handle_conflict_escalate,
            MessageType.RESOLUTION: self._handle_resolution,
            MessageType.PROTOCOL_ERROR: self._handle_protocol_error,
        }[message.message_type]
        return handler(message)

    def _validate_message(self, message: Envelope) -> Envelope | None:
        if message.protocol != "MPAC":
            return self._protocol_error("MALFORMED_MESSAGE", message, "protocol must be MPAC")
        if (
            message.message_type != MessageType.HELLO
            and message.sender.principal_type != PrincipalType.SERVICE
            and message.sender.principal_id not in self.session.participants
        ):
            return self._protocol_error("INVALID_REFERENCE", message, "participant must send HELLO first")
        return None

    def _handle_hello(self, message: Envelope) -> list[Envelope]:
        payload: HelloPayload = message.payload
        principal = Principal(
            principal_id=message.sender.principal_id,
            principal_type=message.sender.principal_type,
            display_name=payload.display_name,
            roles=[Role(role) for role in payload.roles],
            capabilities=list(payload.capabilities),
            implementation=dict(payload.implementation),
        )
        self.session.participants[principal.principal_id] = ParticipantPresence(
            principal=principal,
            status=PresenceStatus.IDLE,
            joined=True,
            last_seen=self.session.lamport_clock,
        )
        return []

    def _handle_heartbeat(self, message: Envelope) -> list[Envelope]:
        payload: HeartbeatPayload = message.payload
        presence = self.session.participants[message.sender.principal_id]
        presence.status = PresenceStatus(payload.status)
        presence.active_intent_id = payload.active_intent_id
        presence.summary = payload.summary
        presence.last_seen = self.session.lamport_clock
        return []

    def _handle_goodbye(self, message: Envelope) -> list[Envelope]:
        payload: GoodbyePayload = message.payload
        presence = self.session.participants[message.sender.principal_id]
        presence.joined = False
        presence.status = PresenceStatus.OFFLINE
        presence.last_seen = self.session.lamport_clock
        if payload.intent_disposition == "withdraw":
            for intent_id in payload.active_intents:
                if intent_id in self.session.intents:
                    self.session.intents[intent_id].state = IntentState.WITHDRAWN
        return []

    def _handle_intent_announce(self, message: Envelope) -> list[Envelope]:
        payload: IntentAnnouncePayload = message.payload
        principal = self.session.participants[message.sender.principal_id].principal
        if not self.governor.can_announce_intent(principal):
            return [self._protocol_error("AUTHORIZATION_FAILED", message, "principal cannot announce intent")]

        intent = Intent(
            intent_id=payload.intent_id,
            principal_id=message.sender.principal_id,
            objective=payload.objective,
            scope=payload.scope,
            assumptions=list(payload.assumptions),
            priority=payload.priority,
            ttl_sec=payload.ttl_sec,
            state=IntentState.ACTIVE,
            created_at_tick=self.session.lamport_clock,
            updated_at_tick=self.session.lamport_clock,
        )
        self.session.intents[intent.intent_id] = intent
        self.session.participants[message.sender.principal_id].active_intent_id = intent.intent_id
        if not self.auto_detect_conflicts:
            return []
        return self._emit_conflicts(self.detector.detect_for_intent(self.session, intent))

    def _handle_intent_update(self, message: Envelope) -> list[Envelope]:
        payload: IntentUpdatePayload = message.payload
        intent = self.session.intents.get(payload.intent_id)
        if intent is None:
            return [self._protocol_error("INVALID_REFERENCE", message, "unknown intent")]
        if payload.objective is not None:
            intent.objective = payload.objective
        if payload.scope is not None:
            intent.scope = payload.scope
        if payload.assumptions is not None:
            intent.assumptions = list(payload.assumptions)
        if payload.ttl_sec is not None:
            intent.ttl_sec = payload.ttl_sec
        intent.updated_at_tick = self.session.lamport_clock
        intent.state = IntentState.ACTIVE
        if not self.auto_detect_conflicts:
            return []
        return self._emit_conflicts(self.detector.detect_for_intent(self.session, intent))

    def _handle_intent_withdraw(self, message: Envelope) -> list[Envelope]:
        payload: IntentWithdrawPayload = message.payload
        intent = self.session.intents.get(payload.intent_id)
        if intent is None:
            return [self._protocol_error("INVALID_REFERENCE", message, "unknown intent")]
        intent.state = IntentState.WITHDRAWN
        return []

    def _handle_op_propose(self, message: Envelope) -> list[Envelope]:
        payload: OperationPayload = message.payload
        principal = self.session.participants[message.sender.principal_id].principal
        if not self.governor.can_propose(principal):
            return [self._protocol_error("AUTHORIZATION_FAILED", message, "principal cannot propose operations")]
        operation = Operation(
            op_id=payload.op_id,
            principal_id=message.sender.principal_id,
            target=payload.target,
            op_kind=payload.op_kind,
            intent_id=payload.intent_id,
            state_ref_before=payload.state_ref_before,
            state_ref_after=payload.state_ref_after,
            change_ref=payload.change_ref,
            summary=payload.summary,
            state=OperationState.PROPOSED,
            created_at_tick=self.session.lamport_clock,
            updated_at_tick=self.session.lamport_clock,
        )
        self.session.operations[operation.op_id] = operation
        return self._post_operation_checks(operation)

    def _handle_op_commit(self, message: Envelope) -> list[Envelope]:
        payload: OperationPayload = message.payload
        principal = self.session.participants[message.sender.principal_id].principal
        if not self.governor.can_commit(principal, self.session):
            return [self._protocol_error("AUTHORIZATION_FAILED", message, "principal cannot commit operations")]
        operation = self.session.operations.get(payload.op_id)
        if operation is None:
            operation = Operation(
                op_id=payload.op_id,
                principal_id=message.sender.principal_id,
                target=payload.target,
                op_kind=payload.op_kind,
                intent_id=payload.intent_id,
                created_at_tick=self.session.lamport_clock,
            )
            self.session.operations[operation.op_id] = operation
        operation.state = OperationState.COMMITTED
        operation.state_ref_before = payload.state_ref_before
        operation.state_ref_after = payload.state_ref_after
        operation.change_ref = payload.change_ref
        operation.summary = payload.summary
        operation.updated_at_tick = self.session.lamport_clock
        self.session.shared_state[operation.target] = operation.state_ref_after or operation.change_ref or operation.op_id
        return self._post_operation_checks(operation)

    def _handle_op_reject(self, message: Envelope) -> list[Envelope]:
        payload: OperationRejectPayload = message.payload
        principal = self.session.participants[message.sender.principal_id].principal
        if not self.governor.can_reject(principal):
            return [self._protocol_error("AUTHORIZATION_FAILED", message, "principal cannot reject operations")]
        operation = self.session.operations.get(payload.op_id)
        if operation is None:
            return [self._protocol_error("INVALID_REFERENCE", message, "unknown operation")]
        operation.state = OperationState.REJECTED
        operation.updated_at_tick = self.session.lamport_clock
        return []

    def _handle_op_supersede(self, message: Envelope) -> list[Envelope]:
        payload: OperationSupersedePayload = message.payload
        superseded = self.session.operations.get(payload.supersedes_op_id)
        if superseded is None or superseded.state != OperationState.COMMITTED:
            return [self._protocol_error("INVALID_REFERENCE", message, "superseded operation must already be committed")]
        operation = Operation(
            op_id=payload.op_id,
            principal_id=message.sender.principal_id,
            target=payload.target,
            op_kind="supersede",
            intent_id=payload.intent_id,
            summary=payload.reason,
            state=OperationState.COMMITTED,
            created_at_tick=self.session.lamport_clock,
            updated_at_tick=self.session.lamport_clock,
            supersedes_op_id=payload.supersedes_op_id,
        )
        superseded.state = OperationState.SUPERSEDED
        self.session.operations[operation.op_id] = operation
        return []

    def _handle_conflict_report(self, message: Envelope) -> list[Envelope]:
        payload: ConflictReportPayload = message.payload
        conflict = Conflict(
            conflict_id=payload.conflict_id,
            reporter_id=message.sender.principal_id,
            category=ConflictCategory(payload.category),
            severity=Severity(payload.severity),
            basis=payload.basis,
            description=payload.description,
            suggested_action=payload.suggested_action,
            related_intents=list(payload.related_intents),
            related_ops=list(payload.related_ops),
            based_on_watermark=payload.based_on_watermark,
        )
        self.session.conflicts[conflict.conflict_id] = conflict
        return []

    def _handle_conflict_ack(self, message: Envelope) -> list[Envelope]:
        payload: ConflictAckPayload = message.payload
        conflict = self.session.conflicts.get(payload.conflict_id)
        if conflict is None:
            return [self._protocol_error("INVALID_REFERENCE", message, "unknown conflict")]
        conflict.state = ConflictState.ACKED
        return []

    def _handle_conflict_escalate(self, message: Envelope) -> list[Envelope]:
        payload: ConflictEscalatePayload = message.payload
        conflict = self.session.conflicts.get(payload.conflict_id)
        if conflict is None:
            return [self._protocol_error("INVALID_REFERENCE", message, "unknown conflict")]
        conflict.state = ConflictState.ESCALATED
        return []

    def _handle_resolution(self, message: Envelope) -> list[Envelope]:
        payload: ResolutionPayload = message.payload
        principal = self.session.participants[message.sender.principal_id].principal
        if not self.governor.can_resolve(principal):
            return [self._protocol_error("AUTHORIZATION_FAILED", message, "principal cannot resolve conflicts")]
        if payload.conflict_id not in self.session.conflicts:
            return [self._protocol_error("INVALID_REFERENCE", message, "unknown conflict")]
        resolution = Resolution(
            resolution_id=payload.resolution_id,
            conflict_id=payload.conflict_id,
            decision=payload.decision,
            outcome=payload.outcome,
            rationale=payload.rationale,
            resolver_id=message.sender.principal_id,
        )
        self.session.resolutions[resolution.resolution_id] = resolution
        self.governor.apply_resolution(self.session, resolution)
        return []

    def _handle_protocol_error(self, message: Envelope) -> list[Envelope]:
        return []

    def _post_operation_checks(self, operation: Operation) -> list[Envelope]:
        if not self.auto_detect_conflicts:
            return []
        responses = self._emit_conflicts(self.detector.detect_for_operation(self.session, operation))
        if operation.intent_id and operation.intent_id in self.session.intents:
            conflict = self.detector.detect_scope_violation(self.session, self.session.intents[operation.intent_id], operation)
            if conflict is not None:
                responses.extend(self._emit_conflicts([conflict]))
        return responses

    def _emit_conflicts(self, conflicts: list[Conflict]) -> list[Envelope]:
        responses: list[Envelope] = []
        for conflict in conflicts:
            self.session.conflicts[conflict.conflict_id] = conflict
            report = Envelope(
                message_type=MessageType.CONFLICT_REPORT,
                session_id=self.session.session_id,
                sender=SenderRef(principal_id=conflict.reporter_id, principal_type=PrincipalType.SERVICE),
                payload=ConflictReportPayload(
                    conflict_id=conflict.conflict_id,
                    related_intents=list(conflict.related_intents),
                    related_ops=list(conflict.related_ops),
                    category=conflict.category.value,
                    severity=conflict.severity.value,
                    basis=conflict.basis,
                    description=conflict.description,
                    suggested_action=conflict.suggested_action,
                    based_on_watermark=conflict.based_on_watermark,
                ),
            )
            responses.append(report)

            auto_resolution = self.governor.maybe_auto_resolution(self.session, conflict)
            if auto_resolution is not None:
                self.session.resolutions[auto_resolution.resolution_id] = auto_resolution
                self.governor.apply_resolution(self.session, auto_resolution)
                responses.append(
                    Envelope(
                        message_type=MessageType.RESOLUTION,
                        session_id=self.session.session_id,
                        sender=SenderRef(principal_id=auto_resolution.resolver_id, principal_type=PrincipalType.SERVICE),
                        payload=ResolutionPayload(
                            resolution_id=auto_resolution.resolution_id,
                            conflict_id=auto_resolution.conflict_id,
                            decision=auto_resolution.decision,
                            outcome=auto_resolution.outcome,
                            rationale=auto_resolution.rationale,
                        ),
                    )
                )

            if self.governor.should_auto_escalate(self.session, conflict):
                target = self.governor.escalation_target(self.session)
                if target:
                    conflict.state = ConflictState.ESCALATED
                    responses.append(
                        Envelope(
                            message_type=MessageType.CONFLICT_ESCALATE,
                            session_id=self.session.session_id,
                            sender=SenderRef(principal_id="service:governor", principal_type=PrincipalType.SERVICE),
                            payload=ConflictEscalatePayload(
                                conflict_id=conflict.conflict_id,
                                escalate_to=target,
                                reason="auto_escalation_high_severity",
                                context=conflict.description,
                            ),
                        )
                    )
        return responses

    def _protocol_error(self, code: str, message: Envelope, description: str) -> Envelope:
        return Envelope(
            message_type=MessageType.PROTOCOL_ERROR,
            session_id=self.session.session_id,
            sender=SenderRef(principal_id="service:runtime", principal_type=PrincipalType.SERVICE),
            payload=ProtocolErrorPayload(error_code=code, refers_to=message.message_id, description=description),
            in_reply_to=message.message_id,
        )

    def _expire_intents(self) -> None:
        for intent in self.session.intents.values():
            if intent.state not in {IntentState.ANNOUNCED, IntentState.ACTIVE}:
                continue
            age = self.session.lamport_clock - intent.created_at_tick
            if age >= intent.ttl_sec:
                intent.state = IntentState.EXPIRED

    def _audit(self, message: Envelope) -> None:
        self.session.message_log.append(message.to_dict())

    def _serialize(self, value: Any) -> Any:
        if is_dataclass(value):
            return {key: self._serialize(item) for key, item in asdict(value).items()}
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, list):
            return [self._serialize(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize(item) for key, item in value.items()}
        return value
