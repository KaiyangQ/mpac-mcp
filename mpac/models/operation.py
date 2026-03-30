"""Operation models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OperationState(str, Enum):
    PROPOSED = "PROPOSED"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


@dataclass
class Operation:
    op_id: str
    principal_id: str
    target: str
    op_kind: str
    intent_id: str | None = None
    state_ref_before: str | None = None
    state_ref_after: str | None = None
    change_ref: str | None = None
    summary: str = ""
    state: OperationState = OperationState.PROPOSED
    created_at_tick: int = 0
    updated_at_tick: int = 0
    supersedes_op_id: str | None = None
