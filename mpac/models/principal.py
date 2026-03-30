"""Principal and presence models for MPAC."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


class PrincipalType(str, Enum):
    HUMAN = "human"
    AGENT = "agent"
    SERVICE = "service"


class Role(str, Enum):
    OBSERVER = "observer"
    CONTRIBUTOR = "contributor"
    REVIEWER = "reviewer"
    OWNER = "owner"
    ARBITER = "arbiter"


class PresenceStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    BLOCKED = "blocked"
    AWAITING_REVIEW = "awaiting_review"
    OFFLINE = "offline"


@dataclass
class Principal:
    principal_id: str
    principal_type: PrincipalType
    display_name: str
    roles: list[Role] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    implementation: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass
class ParticipantPresence:
    principal: Principal
    status: PresenceStatus = PresenceStatus.IDLE
    joined: bool = True
    active_intent_id: str | None = None
    summary: str | None = None
    last_seen: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)
