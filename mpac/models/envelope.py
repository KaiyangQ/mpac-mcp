"""Envelope and watermark definitions for MPAC messages."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .principal import PrincipalType


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


class MessageType(str, Enum):
    HELLO = "HELLO"
    HEARTBEAT = "HEARTBEAT"
    GOODBYE = "GOODBYE"
    INTENT_ANNOUNCE = "INTENT_ANNOUNCE"
    INTENT_UPDATE = "INTENT_UPDATE"
    INTENT_WITHDRAW = "INTENT_WITHDRAW"
    OP_PROPOSE = "OP_PROPOSE"
    OP_COMMIT = "OP_COMMIT"
    OP_REJECT = "OP_REJECT"
    OP_SUPERSEDE = "OP_SUPERSEDE"
    CONFLICT_REPORT = "CONFLICT_REPORT"
    CONFLICT_ACK = "CONFLICT_ACK"
    CONFLICT_ESCALATE = "CONFLICT_ESCALATE"
    RESOLUTION = "RESOLUTION"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"


@dataclass
class SenderRef:
    principal_id: str
    principal_type: PrincipalType


@dataclass
class Watermark:
    kind: str
    value: Any
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class Envelope:
    message_type: MessageType
    session_id: str
    sender: SenderRef
    payload: Any
    protocol: str = "MPAC"
    version: str = "0.1.0"
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    watermark: Watermark | None = None
    in_reply_to: str | None = None
    trace_id: str | None = None
    policy_ref: str | None = None
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "protocol": self.protocol,
            "version": self.version,
            "message_type": self.message_type.value,
            "message_id": self.message_id,
            "session_id": self.session_id,
            "sender": _serialize(self.sender),
            "ts": self.ts,
            "payload": _serialize(self.payload),
        }
        if self.watermark is not None:
            data["watermark"] = _serialize(self.watermark)
        if self.in_reply_to is not None:
            data["in_reply_to"] = self.in_reply_to
        if self.trace_id is not None:
            data["trace_id"] = self.trace_id
        if self.policy_ref is not None:
            data["policy_ref"] = self.policy_ref
        if self.extensions:
            data["extensions"] = _serialize(self.extensions)
        return data
