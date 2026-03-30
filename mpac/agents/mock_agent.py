"""Mock agents for driving the reference runtime."""

from __future__ import annotations

from dataclasses import dataclass, field

from mpac.models import (
    Decision,
    Envelope,
    MessageType,
    Outcome,
    Principal,
    PrincipalType,
    ResolutionPayload,
    Role,
    SenderRef,
)
from mpac.runtime.session import SessionState


@dataclass
class MockAgent:
    principal: Principal
    auto_resolve_escalations: bool = False
    handled_conflicts: set[str] = field(default_factory=set)

    @property
    def principal_id(self) -> str:
        return self.principal.principal_id

    def handle(self, message: Envelope, session: SessionState) -> list[Envelope]:
        if (
            self.auto_resolve_escalations
            and message.message_type == MessageType.CONFLICT_ESCALATE
            and message.payload.escalate_to == self.principal.principal_id
            and message.payload.conflict_id not in self.handled_conflicts
            and any(role in self.principal.roles for role in (Role.OWNER, Role.ARBITER))
        ):
            self.handled_conflicts.add(message.payload.conflict_id)
            conflict = session.conflicts[message.payload.conflict_id]
            accepted = conflict.related_intents[:1] or conflict.related_ops[:1]
            rejected = conflict.related_intents[1:] or conflict.related_ops[1:]
            return [
                Envelope(
                    message_type=MessageType.RESOLUTION,
                    session_id=session.session_id,
                    sender=SenderRef(
                        principal_id=self.principal.principal_id,
                        principal_type=self.principal.principal_type,
                    ),
                    payload=ResolutionPayload(
                        resolution_id=f"res-{message.payload.conflict_id}",
                        conflict_id=message.payload.conflict_id,
                        decision=Decision.HUMAN_OVERRIDE,
                        outcome=Outcome(accepted=accepted, rejected=rejected, merged=[]),
                        rationale=f"{self.principal.display_name} resolved escalated conflict.",
                    ),
                    in_reply_to=message.message_id,
                )
            ]
        return []
