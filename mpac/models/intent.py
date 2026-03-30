"""Intent and scope models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ScopeKind(str, Enum):
    FILE_SET = "file_set"
    RESOURCE_PATH = "resource_path"
    TASK_SET = "task_set"
    QUERY = "query"
    ENTITY_SET = "entity_set"
    CUSTOM = "custom"


class IntentState(str, Enum):
    DRAFT = "DRAFT"
    ANNOUNCED = "ANNOUNCED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    WITHDRAWN = "WITHDRAWN"


@dataclass
class Scope:
    kind: ScopeKind
    resources: list[str] = field(default_factory=list)
    pattern: str | None = None
    task_ids: list[str] = field(default_factory=list)
    expression: str | None = None
    language: str | None = None
    entities: list[str] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)

    def targets(self) -> set[str]:
        if self.kind == ScopeKind.FILE_SET:
            return set(self.resources)
        if self.kind == ScopeKind.TASK_SET:
            return set(self.task_ids)
        if self.kind == ScopeKind.ENTITY_SET:
            return set(self.entities)
        if self.kind == ScopeKind.RESOURCE_PATH and self.pattern:
            return {self.pattern}
        if self.kind == ScopeKind.QUERY and self.expression:
            return {self.expression}
        return set()

    def contains(self, target: str) -> bool:
        targets = self.targets()
        return not targets or target in targets


@dataclass
class Intent:
    intent_id: str
    principal_id: str
    objective: str
    scope: Scope
    assumptions: list[str] = field(default_factory=list)
    priority: str = "normal"
    ttl_sec: int = 300
    state: IntentState = IntentState.ANNOUNCED
    parent_intent_id: str | None = None
    superseded_intent_id: str | None = None
    created_at_tick: int = 0
    updated_at_tick: int = 0
