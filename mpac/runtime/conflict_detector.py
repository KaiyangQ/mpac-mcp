"""Rule-based conflict detection."""

from __future__ import annotations

import uuid

from mpac.models import (
    Conflict,
    ConflictCategory,
    ConflictState,
    DetectionBasis,
    DetectionBasisKind,
    Intent,
    IntentState,
    Operation,
    OperationState,
    Severity,
    Watermark,
)
from mpac.runtime.session import SessionState


class ConflictDetector:
    """Reference conflict detector using deterministic rules."""

    def detect_for_intent(self, session: SessionState, intent: Intent) -> list[Conflict]:
        conflicts: list[Conflict] = []
        targets = intent.scope.targets()
        if not targets:
            return conflicts

        for existing in session.intents.values():
            if existing.intent_id == intent.intent_id or existing.principal_id == intent.principal_id:
                continue
            if existing.state not in {IntentState.ANNOUNCED, IntentState.ACTIVE}:
                continue
            overlap = targets & existing.scope.targets()
            if overlap:
                conflicts.append(
                    self._conflict(
                        category=ConflictCategory.SCOPE_OVERLAP,
                        severity=Severity.HIGH,
                        description=(
                            f"Intent scope overlap on {sorted(overlap)} between "
                            f"{existing.intent_id} and {intent.intent_id}."
                        ),
                        suggested_action="human_review",
                        related_intents=[existing.intent_id, intent.intent_id],
                        session=session,
                        rule_id="scope.overlap.v1",
                    )
                )

            if self._has_assumption_contradiction(existing.assumptions, intent.assumptions):
                conflicts.append(
                    self._conflict(
                        category=ConflictCategory.ASSUMPTION_CONTRADICTION,
                        severity=Severity.MEDIUM,
                        description=f"Contradictory assumptions detected between {existing.intent_id} and {intent.intent_id}.",
                        suggested_action="review_assumptions",
                        related_intents=[existing.intent_id, intent.intent_id],
                        session=session,
                        rule_id="assumptions.contradiction.v1",
                    )
                )
        return conflicts

    def detect_for_operation(self, session: SessionState, operation: Operation) -> list[Conflict]:
        conflicts: list[Conflict] = []
        for existing in session.operations.values():
            if existing.op_id == operation.op_id or existing.principal_id == operation.principal_id:
                continue
            if existing.target != operation.target:
                continue
            if existing.state not in {OperationState.PROPOSED, OperationState.COMMITTED}:
                continue
            conflicts.append(
                self._conflict(
                    category=ConflictCategory.CONCURRENT_WRITE,
                    severity=Severity.HIGH,
                    description=f"Concurrent operations {existing.op_id} and {operation.op_id} both target {operation.target}.",
                    suggested_action="human_review",
                    related_intents=[item for item in [existing.intent_id, operation.intent_id] if item],
                    related_ops=[existing.op_id, operation.op_id],
                    session=session,
                    rule_id="ops.concurrent_write.v1",
                )
            )
        return conflicts

    def detect_scope_violation(self, session: SessionState, intent: Intent, operation: Operation) -> Conflict | None:
        if intent.scope.contains(operation.target):
            return None
        return self._conflict(
            category=ConflictCategory.POLICY_VIOLATION,
            severity=Severity.MEDIUM,
            description=f"Operation {operation.op_id} targets {operation.target} outside intent {intent.intent_id} scope.",
            suggested_action="reject_or_revise",
            related_intents=[intent.intent_id],
            related_ops=[operation.op_id],
            session=session,
            rule_id="intent.scope_consistency.v1",
        )

    def _has_assumption_contradiction(self, left: list[str], right: list[str]) -> bool:
        lowered_left = {item.lower() for item in left}
        lowered_right = {item.lower() for item in right}
        for item in lowered_left:
            if item.startswith("not ") and item[4:] in lowered_right:
                return True
        for item in lowered_right:
            if item.startswith("not ") and item[4:] in lowered_left:
                return True
        return False

    def _conflict(
        self,
        *,
        category: ConflictCategory,
        severity: Severity,
        description: str,
        suggested_action: str,
        session: SessionState,
        rule_id: str,
        related_intents: list[str] | None = None,
        related_ops: list[str] | None = None,
    ) -> Conflict:
        return Conflict(
            conflict_id=f"conf-{uuid.uuid4().hex[:8]}",
            reporter_id="service:conflict-detector",
            category=category,
            severity=severity,
            basis=DetectionBasis(kind=DetectionBasisKind.RULE, rule_id=rule_id),
            description=description,
            suggested_action=suggested_action,
            related_intents=related_intents or [],
            related_ops=related_ops or [],
            based_on_watermark=Watermark(kind="lamport_clock", value=session.lamport_clock),
            state=ConflictState.OPEN,
        )
