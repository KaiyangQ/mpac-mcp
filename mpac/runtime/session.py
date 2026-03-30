"""In-memory session state."""

from __future__ import annotations

from dataclasses import dataclass, field

from mpac.models import Conflict, GovernancePolicy, Intent, Operation, ParticipantPresence, Resolution


@dataclass
class SessionState:
    session_id: str
    version: str = "0.1.0"
    governance_policy: GovernancePolicy = field(default_factory=GovernancePolicy)
    participants: dict[str, ParticipantPresence] = field(default_factory=dict)
    intents: dict[str, Intent] = field(default_factory=dict)
    operations: dict[str, Operation] = field(default_factory=dict)
    conflicts: dict[str, Conflict] = field(default_factory=dict)
    resolutions: dict[str, Resolution] = field(default_factory=dict)
    shared_state: dict[str, str] = field(default_factory=dict)
    message_log: list[dict] = field(default_factory=list)
    lamport_clock: int = 0

    def tick(self) -> int:
        self.lamport_clock += 1
        return self.lamport_clock
