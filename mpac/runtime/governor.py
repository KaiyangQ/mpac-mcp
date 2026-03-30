"""Role-aware governance checks and resolution helpers."""

from __future__ import annotations

from mpac.models import (
    Conflict,
    ConflictState,
    Decision,
    GovernanceMode,
    IntentState,
    Operation,
    OperationState,
    Outcome,
    Principal,
    Resolution,
    Role,
    Severity,
)
from mpac.runtime.session import SessionState


class GovernanceEngine:
    def can_announce_intent(self, principal: Principal) -> bool:
        return self._has_cap(principal, "intent.broadcast") or self._has_role(
            principal, Role.CONTRIBUTOR, Role.OWNER, Role.ARBITER
        )

    def can_propose(self, principal: Principal) -> bool:
        return self._has_cap(principal, "op.propose") or self._has_role(
            principal, Role.CONTRIBUTOR, Role.REVIEWER, Role.OWNER, Role.ARBITER
        )

    def can_commit(self, principal: Principal, session: SessionState) -> bool:
        if session.governance_policy.mode == GovernanceMode.REVIEW_REQUIRED:
            return self._has_role(principal, Role.REVIEWER, Role.OWNER, Role.ARBITER) or self._has_cap(
                principal, "governance.override"
            )
        return self._has_cap(principal, "op.commit") or self._has_role(
            principal, Role.CONTRIBUTOR, Role.REVIEWER, Role.OWNER, Role.ARBITER
        )

    def can_reject(self, principal: Principal) -> bool:
        return self._has_cap(principal, "op.reject") or self._has_role(principal, Role.REVIEWER, Role.OWNER, Role.ARBITER)

    def can_resolve(self, principal: Principal) -> bool:
        return self._has_cap(principal, "governance.override") or self._has_role(principal, Role.OWNER, Role.ARBITER)

    def maybe_auto_resolution(self, session: SessionState, conflict: Conflict) -> Resolution | None:
        if not session.governance_policy.auto_resolve_low_severity:
            return None
        if conflict.severity not in {Severity.INFO, Severity.LOW, Severity.MEDIUM}:
            return None
        return Resolution(
            resolution_id=f"res-auto-{conflict.conflict_id}",
            conflict_id=conflict.conflict_id,
            decision=Decision.DEFERRED,
            outcome=Outcome(),
            rationale="Automatically deferred for later review.",
            resolver_id="service:governor",
        )

    def should_auto_escalate(self, session: SessionState, conflict: Conflict) -> bool:
        order = {
            Severity.INFO: 0,
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 3,
            Severity.CRITICAL: 4,
        }
        return order[conflict.severity] >= order[session.governance_policy.escalation_threshold]

    def escalation_target(self, session: SessionState) -> str | None:
        for presence in session.participants.values():
            if Role.ARBITER in presence.principal.roles and presence.joined:
                return presence.principal.principal_id
        for presence in session.participants.values():
            if Role.OWNER in presence.principal.roles and presence.joined:
                return presence.principal.principal_id
        return None

    def apply_resolution(self, session: SessionState, resolution: Resolution) -> None:
        conflict = session.conflicts[resolution.conflict_id]
        if resolution.decision == Decision.DISMISSED:
            conflict.state = ConflictState.DISMISSED
            return
        conflict.state = ConflictState.RESOLVED

        for identifier in resolution.outcome.accepted:
            if identifier in session.intents:
                session.intents[identifier].state = IntentState.ACTIVE
            if identifier in session.operations and session.operations[identifier].state == OperationState.PROPOSED:
                session.operations[identifier].state = OperationState.COMMITTED

        for identifier in resolution.outcome.rejected:
            if identifier in session.intents:
                session.intents[identifier].state = IntentState.WITHDRAWN
            if identifier in session.operations:
                session.operations[identifier].state = OperationState.REJECTED

        for identifier in resolution.outcome.merged:
            if identifier in session.operations:
                session.operations[identifier].state = OperationState.SUPERSEDED

        conflict.state = ConflictState.CLOSED

    def _has_cap(self, principal: Principal, capability: str) -> bool:
        return capability in principal.capabilities

    def _has_role(self, principal: Principal, *roles: Role) -> bool:
        return any(role in principal.roles for role in roles)
