"""Executable reference scenarios based on Appendix A of the MPAC spec."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mpac import MPACRuntime
from mpac.models import (
    ConflictAckPayload,
    ConflictEscalatePayload,
    ConflictReportPayload,
    Decision,
    DetectionBasis,
    DetectionBasisKind,
    GoodbyePayload,
    GovernanceMode,
    HelloPayload,
    IntentAnnouncePayload,
    IntentUpdatePayload,
    IntentWithdrawPayload,
    MessageType,
    OperationPayload,
    OperationRejectPayload,
    OperationSupersedePayload,
    Outcome,
    PrincipalType,
    ResolutionPayload,
    Scope,
    ScopeKind,
)


@dataclass
class ScenarioCase:
    scenario_id: str
    title: str
    summary: str
    assessment: str
    notes: list[str]
    runner: Callable[[], dict[str, Any]]
    validator: Callable[[dict[str, Any]], None]


class ScenarioDriver:
    def __init__(self, session_id: str, *, review_required: bool = False) -> None:
        self.runtime = MPACRuntime(session_id=session_id, auto_detect_conflicts=False)
        self.runtime.session.governance_policy.auto_resolve_low_severity = False
        if review_required:
            self.runtime.session.governance_policy.mode = GovernanceMode.REVIEW_REQUIRED

    def send(self, message_type: MessageType, sender_id: str, sender_type: PrincipalType, payload: Any) -> None:
        self.runtime.receive(
            self.runtime.make_envelope(
                message_type=message_type,
                sender_id=sender_id,
                sender_type=sender_type,
                payload=payload,
            )
        )

    def hello(self, sender_id: str, sender_type: PrincipalType, display_name: str, roles: list[str], capabilities: list[str]) -> None:
        self.send(
            MessageType.HELLO,
            sender_id,
            sender_type,
            HelloPayload(
                display_name=display_name,
                roles=roles,
                capabilities=capabilities,
                implementation={"name": "mpac-scenarios", "version": "0.1.0"},
            ),
        )

    def conflict_report(
        self,
        sender_id: str,
        conflict_id: str,
        related_intents: list[str],
        related_ops: list[str],
        category: str,
        severity: str,
        basis_kind: DetectionBasisKind,
        description: str,
        suggested_action: str,
        sender_type: PrincipalType = PrincipalType.AGENT,
    ) -> None:
        self.send(
            MessageType.CONFLICT_REPORT,
            sender_id,
            sender_type,
            ConflictReportPayload(
                conflict_id=conflict_id,
                related_intents=related_intents,
                related_ops=related_ops,
                category=category,
                severity=severity,
                basis=DetectionBasis(kind=basis_kind),
                description=description,
                suggested_action=suggested_action,
                based_on_watermark=None,
            ),
        )

    def resolution(
        self,
        sender_id: str,
        conflict_id: str,
        resolution_id: str,
        decision: Decision,
        accepted: list[str] | None = None,
        rejected: list[str] | None = None,
        merged: list[str] | None = None,
        rationale: str = "",
        sender_type: PrincipalType = PrincipalType.HUMAN,
    ) -> None:
        self.send(
            MessageType.RESOLUTION,
            sender_id,
            sender_type,
            ResolutionPayload(
                resolution_id=resolution_id,
                conflict_id=conflict_id,
                decision=decision,
                outcome=Outcome(
                    accepted=accepted or [],
                    rejected=rejected or [],
                    merged=merged or [],
                ),
                rationale=rationale,
            ),
        )

    def snapshot(self) -> dict[str, Any]:
        return self.runtime.snapshot()


def _scenario_1() -> dict[str, Any]:
    driver = ScenarioDriver("sess-registration-feature")
    driver.hello("human:maya", PrincipalType.HUMAN, "Maya Chen", ["owner", "arbiter"], ["governance.override", "conflict.report"])
    driver.hello("agent:backend-1", PrincipalType.AGENT, "Backend Agent", ["contributor"], ["intent.broadcast", "intent.update", "op.commit", "conflict.report"])
    driver.hello("agent:db-1", PrincipalType.AGENT, "Database Agent", ["contributor"], ["intent.broadcast", "op.commit", "conflict.report"])

    driver.send(
        MessageType.INTENT_ANNOUNCE,
        "agent:backend-1",
        PrincipalType.AGENT,
        IntentAnnouncePayload(
            intent_id="intent-api-endpoint",
            objective="Create POST /api/v1/register endpoint with input validation and password hashing",
            scope=Scope(kind=ScopeKind.FILE_SET, resources=["src/routes/auth.ts", "src/validators/registration.ts", "src/services/user-service.ts"]),
            assumptions=["user.id is integer", "bcrypt is the agreed hashing algorithm", "Email uniqueness is enforced at the database level"],
            ttl_sec=300,
        ),
    )
    driver.send(
        MessageType.INTENT_ANNOUNCE,
        "agent:db-1",
        PrincipalType.AGENT,
        IntentAnnouncePayload(
            intent_id="intent-db-schema",
            objective="Create users table migration and add unique index on email",
            scope=Scope(kind=ScopeKind.FILE_SET, resources=["migrations/003_create_users.sql", "src/models/user.ts"]),
            assumptions=["Using PostgreSQL 15", "password_hash column is VARCHAR(255) for bcrypt output", "user.id is UUID"],
            ttl_sec=300,
        ),
    )
    driver.conflict_report(
        "agent:db-1",
        "conf-id-type",
        ["intent-api-endpoint", "intent-db-schema"],
        [],
        "assumption_contradiction",
        "high",
        DetectionBasisKind.MODEL_INFERENCE,
        "Backend agent assumes integer IDs while database schema uses UUIDs.",
        "human_review",
    )
    driver.resolution(
        "human:maya",
        "conf-id-type",
        "res-id-type",
        Decision.HUMAN_OVERRIDE,
        accepted=["intent-db-schema"],
        merged=["intent-api-endpoint"],
        rationale="Use UUID for all entity IDs; backend updates to string-based UUID handling.",
    )
    driver.send(
        MessageType.INTENT_UPDATE,
        "agent:backend-1",
        PrincipalType.AGENT,
        IntentUpdatePayload(
            intent_id="intent-api-endpoint",
            objective="Create POST /api/v1/register endpoint with UUID-based user IDs",
            scope=Scope(kind=ScopeKind.FILE_SET, resources=["src/routes/auth.ts", "src/validators/registration.ts", "src/services/user-service.ts"]),
            assumptions=["user.id is UUID", "bcrypt is the agreed hashing algorithm"],
            ttl_sec=300,
        ),
    )
    driver.send(
        MessageType.OP_COMMIT,
        "agent:db-1",
        PrincipalType.AGENT,
        OperationPayload(
            op_id="op-migration",
            intent_id="intent-db-schema",
            target="migrations/003_create_users.sql",
            op_kind="create",
            state_ref_before="sha256:empty",
            state_ref_after="sha256:migration-v1",
            change_ref="sha256:migration-diff-001",
            summary="Created users table with UUID primary key.",
        ),
    )
    driver.send(
        MessageType.OP_COMMIT,
        "agent:backend-1",
        PrincipalType.AGENT,
        OperationPayload(
            op_id="op-endpoint",
            intent_id="intent-api-endpoint",
            target="src/routes/auth.ts",
            op_kind="create",
            state_ref_before="sha256:empty",
            state_ref_after="sha256:endpoint-v1",
            change_ref="sha256:endpoint-diff-001",
            summary="Created register endpoint using UUID IDs.",
        ),
    )
    return driver.snapshot()


def _validate_1(snapshot: dict[str, Any]) -> None:
    assert snapshot["conflicts"]["conf-id-type"]["state"] == "CLOSED"
    assert snapshot["intents"]["intent-api-endpoint"]["state"] == "ACTIVE"
    assert snapshot["operations"]["op-endpoint"]["state"] == "COMMITTED"


def _scenario_2() -> dict[str, Any]:
    driver = ScenarioDriver("sess-paper-draft")
    driver.hello("human:dr-patel", PrincipalType.HUMAN, "Dr. Patel", ["owner"], ["governance.override"])
    driver.hello("human:dr-liu", PrincipalType.HUMAN, "Dr. Liu", ["owner"], ["governance.override"])
    driver.hello("agent:writer-1", PrincipalType.AGENT, "Writer Agent", ["contributor"], ["intent.broadcast", "op.commit", "conflict.report"])
    driver.hello("agent:viz-1", PrincipalType.AGENT, "Viz Agent", ["contributor"], ["intent.broadcast", "op.commit"])
    driver.hello("agent:cite-1", PrincipalType.AGENT, "Citation Agent", ["contributor"], ["intent.broadcast", "op.commit", "conflict.report"])

    driver.send(
        MessageType.INTENT_ANNOUNCE,
        "agent:writer-1",
        PrincipalType.AGENT,
        IntentAnnouncePayload(
            intent_id="intent-methods-draft",
            objective="Draft Methods section",
            scope=Scope(kind=ScopeKind.ENTITY_SET, entities=["paper.sections.methods", "paper.sections.methods.subsections.*"]),
            assumptions=["ImageNet-1K validation set", "Primary metric is top-1 accuracy"],
            priority="high",
            ttl_sec=600,
        ),
    )
    driver.send(
        MessageType.INTENT_ANNOUNCE,
        "agent:viz-1",
        PrincipalType.AGENT,
        IntentAnnouncePayload(
            intent_id="intent-results-figures",
            objective="Generate figures for Results section",
            scope=Scope(kind=ScopeKind.ENTITY_SET, entities=["paper.figures.fig1", "paper.figures.fig2", "paper.sections.results"]),
            ttl_sec=600,
        ),
    )
    driver.send(
        MessageType.INTENT_ANNOUNCE,
        "agent:cite-1",
        PrincipalType.AGENT,
        IntentAnnouncePayload(
            intent_id="intent-citations",
            objective="Add inline citations and bibliography",
            scope=Scope(kind=ScopeKind.ENTITY_SET, entities=["paper.sections.methods", "paper.sections.related_work", "paper.bibliography"]),
            ttl_sec=600,
        ),
    )
    driver.conflict_report(
        "agent:writer-1",
        "conf-methods-scope",
        ["intent-methods-draft", "intent-citations"],
        [],
        "scope_overlap",
        "medium",
        DetectionBasisKind.RULE,
        "Writer and citation agents both plan to modify Methods.",
        "sequential_execution",
    )
    driver.resolution(
        "human:dr-patel",
        "conf-methods-scope",
        "res-methods-scope",
        Decision.MERGED,
        accepted=["intent-methods-draft", "intent-citations"],
        rationale="Writer drafts first, citation agent adds references after commit.",
    )
    driver.send(
        MessageType.OP_COMMIT,
        "agent:writer-1",
        PrincipalType.AGENT,
        OperationPayload(
            op_id="op-methods-text",
            intent_id="intent-methods-draft",
            target="paper.sections.methods",
            op_kind="replace",
            state_ref_before="sha256:empty-methods",
            state_ref_after="sha256:methods-v1",
            change_ref="sha256:methods-diff-001",
            summary="Drafted Methods section.",
        ),
    )
    driver.send(
        MessageType.OP_COMMIT,
        "agent:cite-1",
        PrincipalType.AGENT,
        OperationPayload(
            op_id="op-methods-citations",
            intent_id="intent-citations",
            target="paper.sections.methods",
            op_kind="replace",
            state_ref_before="sha256:methods-v1",
            state_ref_after="sha256:methods-v2-cited",
            change_ref="sha256:cite-diff-001",
            summary="Inserted citations into Methods.",
        ),
    )
    return driver.snapshot()


def _validate_2(snapshot: dict[str, Any]) -> None:
    assert snapshot["conflicts"]["conf-methods-scope"]["state"] == "CLOSED"
    assert snapshot["shared_state"]["paper.sections.methods"] == "sha256:methods-v2-cited"


def _scenario_3() -> dict[str, Any]:
    driver = ScenarioDriver("sess-incident-4521")
    driver.hello("service:alertmanager", PrincipalType.SERVICE, "Alert Manager", ["observer", "contributor"], ["intent.broadcast", "conflict.report"])
    driver.hello("human:jordan", PrincipalType.HUMAN, "Jordan", ["arbiter"], ["governance.override", "op.reject"])
    driver.hello("agent:diag-1", PrincipalType.AGENT, "Diagnostics Agent", ["contributor"], ["intent.broadcast", "conflict.report"])
    driver.hello("agent:hotfix-1", PrincipalType.AGENT, "Hotfix Agent", ["contributor"], ["intent.broadcast", "op.propose"])

    driver.send(
        MessageType.INTENT_ANNOUNCE,
        "agent:diag-1",
        PrincipalType.AGENT,
        IntentAnnouncePayload(
            intent_id="intent-diagnose",
            objective="Identify root cause of checkout failure spike",
            scope=Scope(kind=ScopeKind.ENTITY_SET, entities=["logs.checkout-service", "metrics.error-rate", "traces.checkout-flow"]),
            assumptions=["No deployments in the last 2 hours"],
            priority="high",
            ttl_sec=180,
        ),
    )
    driver.send(
        MessageType.INTENT_ANNOUNCE,
        "agent:hotfix-1",
        PrincipalType.AGENT,
        IntentAnnouncePayload(
            intent_id="intent-hotfix-cache",
            objective="Flush and rebuild checkout cache",
            scope=Scope(kind=ScopeKind.ENTITY_SET, entities=["service.checkout.cache", "config.cache-ttl"]),
            assumptions=["Root cause is stale cache entries"],
            priority="high",
            ttl_sec=120,
        ),
    )
    driver.send(
        MessageType.OP_PROPOSE,
        "agent:hotfix-1",
        PrincipalType.AGENT,
        OperationPayload(
            op_id="op-cache-flush",
            intent_id="intent-hotfix-cache",
            target="service.checkout.cache",
            op_kind="execute",
            change_ref="runbook:cache-flush-v2",
            summary="Flush checkout session cache and reset TTL.",
        ),
    )
    driver.conflict_report(
        "agent:diag-1",
        "conf-wrong-root-cause",
        ["intent-diagnose", "intent-hotfix-cache"],
        ["op-cache-flush"],
        "assumption_contradiction",
        "critical",
        DetectionBasisKind.MODEL_INFERENCE,
        "Evidence points to payment gateway 502s, not cache.",
        "reject_proposed_op",
    )
    driver.send(
        MessageType.CONFLICT_ESCALATE,
        "agent:diag-1",
        PrincipalType.AGENT,
        ConflictEscalatePayload(
            conflict_id="conf-wrong-root-cause",
            escalate_to="human:jordan",
            reason="critical_severity_production_incident",
            context="Wrong remediation could extend outage.",
        ),
    )
    driver.send(
        MessageType.OP_REJECT,
        "human:jordan",
        PrincipalType.HUMAN,
        OperationRejectPayload(
            op_id="op-cache-flush",
            reason="Wrong root cause. Payment gateway is returning 502s.",
        ),
    )
    driver.resolution(
        "human:jordan",
        "conf-wrong-root-cause",
        "res-root-cause",
        Decision.HUMAN_OVERRIDE,
        accepted=["intent-diagnose"],
        rejected=["intent-hotfix-cache"],
        rationale="Continue diagnosis and pivot hotfix agent to payment gateway investigation.",
    )
    driver.send(
        MessageType.INTENT_WITHDRAW,
        "agent:hotfix-1",
        PrincipalType.AGENT,
        IntentWithdrawPayload(intent_id="intent-hotfix-cache", reason="rejected_by_arbiter"),
    )
    driver.send(
        MessageType.INTENT_ANNOUNCE,
        "agent:hotfix-1",
        PrincipalType.AGENT,
        IntentAnnouncePayload(
            intent_id="intent-investigate-gateway",
            objective="Investigate payment gateway connectivity",
            scope=Scope(kind=ScopeKind.ENTITY_SET, entities=["service.payment-gateway", "config.payment-api-keys", "external.gateway-status"]),
            assumptions=["API keys may have rotated"],
            priority="high",
            ttl_sec=180,
        ),
    )
    return driver.snapshot()


def _validate_3(snapshot: dict[str, Any]) -> None:
    assert snapshot["operations"]["op-cache-flush"]["state"] == "REJECTED"
    assert snapshot["intents"]["intent-hotfix-cache"]["state"] == "WITHDRAWN"
    assert snapshot["intents"]["intent-investigate-gateway"]["state"] == "ACTIVE"


def _scenario_4() -> dict[str, Any]:
    driver = ScenarioDriver("sess-dashboard-feature")
    participants = [
        ("human:alice", PrincipalType.HUMAN, "Alice Wang", ["owner", "reviewer"], ["governance.override", "conflict.report", "op.reject"]),
        ("human:bob", PrincipalType.HUMAN, "Bob Martinez", ["owner", "reviewer"], ["governance.override", "conflict.report", "op.reject"]),
        ("agent:alice-ui", PrincipalType.AGENT, "Alice UI", ["contributor"], ["intent.broadcast", "op.commit", "conflict.report"]),
        ("agent:alice-state", PrincipalType.AGENT, "Alice State", ["contributor"], ["intent.broadcast", "intent.update", "op.commit", "conflict.report"]),
        ("agent:alice-test", PrincipalType.AGENT, "Alice Test", ["contributor"], ["intent.broadcast", "op.commit", "conflict.report"]),
        ("agent:bob-api", PrincipalType.AGENT, "Bob API", ["contributor"], ["intent.broadcast", "op.commit", "conflict.report"]),
        ("agent:bob-db", PrincipalType.AGENT, "Bob DB", ["contributor"], ["intent.broadcast", "op.commit"]),
        ("agent:bob-test", PrincipalType.AGENT, "Bob Test", ["contributor"], ["intent.broadcast", "op.commit", "conflict.report"]),
    ]
    for principal_id, principal_type, display_name, roles, caps in participants:
        driver.hello(principal_id, principal_type, display_name, roles, caps)

    intents = [
        ("agent:bob-db", "intent-db-tables", Scope(kind=ScopeKind.FILE_SET, resources=["migrations/010_dashboard_tables.sql", "src/models/dashboard.py"])),
        ("agent:bob-api", "intent-api-endpoints", Scope(kind=ScopeKind.FILE_SET, resources=["src/routes/dashboard.py", "src/services/dashboard_service.py", "api/dashboard.openapi.yaml"])),
        ("agent:bob-test", "intent-backend-tests", Scope(kind=ScopeKind.FILE_SET, resources=["tests/integration/test_dashboard_api.py"])),
        ("agent:alice-ui", "intent-ui-components", Scope(kind=ScopeKind.FILE_SET, resources=["src/components/Dashboard/DashboardGrid.tsx"])),
        ("agent:alice-state", "intent-state-management", Scope(kind=ScopeKind.FILE_SET, resources=["src/store/dashboardSlice.ts", "src/hooks/useDashboard.ts", "api/dashboard.openapi.yaml"])),
        ("agent:alice-test", "intent-frontend-tests", Scope(kind=ScopeKind.FILE_SET, resources=["src/components/Dashboard/__tests__/DashboardGrid.test.tsx"])),
    ]
    for sender_id, intent_id, scope in intents:
        driver.send(
            MessageType.INTENT_ANNOUNCE,
            sender_id,
            PrincipalType.AGENT,
            IntentAnnouncePayload(intent_id=intent_id, objective=intent_id.replace("-", " "), scope=scope, ttl_sec=600),
        )

    driver.conflict_report(
        "agent:alice-state",
        "conf-openapi-ownership",
        ["intent-api-endpoints", "intent-state-management"],
        [],
        "scope_overlap",
        "high",
        DetectionBasisKind.RULE,
        "Both teams plan to modify api/dashboard.openapi.yaml.",
        "human_review",
    )
    driver.resolution(
        "human:bob",
        "conf-openapi-ownership",
        "res-openapi-v1",
        Decision.MERGED,
        accepted=["intent-api-endpoints"],
        merged=["intent-state-management"],
        rationale="Bob API writes spec first; Alice state consumes it.",
    )
    driver.send(
        MessageType.CONFLICT_ACK,
        "agent:alice-state",
        PrincipalType.AGENT,
        ConflictAckPayload(conflict_id="conf-openapi-ownership", ack_type="disputed"),
    )
    driver.resolution(
        "human:alice",
        "conf-openapi-ownership",
        "res-openapi-v2",
        Decision.MERGED,
        accepted=["intent-api-endpoints", "intent-state-management"],
        rationale="Sequential shared writes to the OpenAPI spec are allowed.",
    )
    driver.send(
        MessageType.CONFLICT_ACK,
        "human:bob",
        PrincipalType.HUMAN,
        ConflictAckPayload(conflict_id="conf-openapi-ownership", ack_type="accepted"),
    )
    commits = [
        ("agent:bob-db", "op-db-migration", "intent-db-tables", "migrations/010_dashboard_tables.sql", "sha256:db-mig-v1"),
        ("agent:bob-api", "op-api-openapi", "intent-api-endpoints", "api/dashboard.openapi.yaml", "sha256:openapi-v1"),
        ("agent:bob-api", "op-api-routes", "intent-api-endpoints", "src/routes/dashboard.py", "sha256:routes-v1"),
        ("agent:alice-ui", "op-ui-components", "intent-ui-components", "src/components/Dashboard/DashboardGrid.tsx", "sha256:grid-v1"),
        ("agent:alice-state", "op-state-slice", "intent-state-management", "src/store/dashboardSlice.ts", "sha256:slice-v1"),
        ("agent:alice-state", "op-openapi-extensions", "intent-state-management", "api/dashboard.openapi.yaml", "sha256:openapi-v2"),
    ]
    before = "sha256:empty"
    for sender_id, op_id, intent_id, target, after in commits:
        driver.send(
            MessageType.OP_COMMIT,
            sender_id,
            PrincipalType.AGENT,
            OperationPayload(
                op_id=op_id,
                intent_id=intent_id,
                target=target,
                op_kind="create" if before == "sha256:empty" else "replace",
                state_ref_before=before if target != "api/dashboard.openapi.yaml" or after != "sha256:openapi-v1" else "sha256:empty",
                state_ref_after=after,
                change_ref=f"{op_id}-diff",
                summary=op_id,
            ),
        )
    driver.conflict_report(
        "agent:bob-test",
        "conf-pagination-mismatch",
        ["intent-api-endpoints", "intent-state-management"],
        ["op-api-routes", "op-state-slice"],
        "assumption_contradiction",
        "high",
        DetectionBasisKind.MODEL_INFERENCE,
        "Routes use offset pagination while the spec and frontend expect cursor pagination.",
        "human_review",
    )
    driver.resolution(
        "human:bob",
        "conf-pagination-mismatch",
        "res-pagination",
        Decision.HUMAN_OVERRIDE,
        merged=["intent-api-endpoints", "intent-state-management"],
        rationale="Spec is correct; backend routes must be fixed to cursor pagination.",
    )
    driver.send(
        MessageType.OP_SUPERSEDE,
        "agent:bob-api",
        PrincipalType.AGENT,
        OperationSupersedePayload(
            op_id="op-api-routes-v2",
            supersedes_op_id="op-api-routes",
            intent_id="intent-api-endpoints",
            target="src/routes/dashboard.py",
            reason="pagination_fix_per_resolution",
        ),
    )
    driver.send(
        MessageType.OP_COMMIT,
        "agent:bob-api",
        PrincipalType.AGENT,
        OperationPayload(
            op_id="op-api-routes-v2",
            intent_id="intent-api-endpoints",
            target="src/routes/dashboard.py",
            op_kind="replace",
            state_ref_before="sha256:routes-v1",
            state_ref_after="sha256:routes-v2",
            change_ref="sha256:routes-fix-diff-001",
            summary="Fixed routes to cursor pagination.",
        ),
    )
    driver.send(
        MessageType.OP_COMMIT,
        "agent:bob-test",
        PrincipalType.AGENT,
        OperationPayload(
            op_id="op-backend-tests",
            intent_id="intent-backend-tests",
            target="tests/integration/test_dashboard_api.py",
            op_kind="create",
            state_ref_before="sha256:empty",
            state_ref_after="sha256:btests-v1",
            change_ref="sha256:btest-diff-001",
            summary="Wrote backend integration tests.",
        ),
    )
    driver.send(
        MessageType.OP_COMMIT,
        "agent:alice-test",
        PrincipalType.AGENT,
        OperationPayload(
            op_id="op-frontend-tests",
            intent_id="intent-frontend-tests",
            target="src/components/Dashboard/__tests__/DashboardGrid.test.tsx",
            op_kind="create",
            state_ref_before="sha256:empty",
            state_ref_after="sha256:ftests-v1",
            change_ref="sha256:ftest-diff-001",
            summary="Wrote frontend tests.",
        ),
    )
    driver.send(
        MessageType.GOODBYE,
        "agent:bob-test",
        PrincipalType.AGENT,
        GoodbyePayload(reason="session_complete", active_intents=[], intent_disposition="withdraw"),
    )
    return driver.snapshot()


def _validate_4(snapshot: dict[str, Any]) -> None:
    assert snapshot["conflicts"]["conf-openapi-ownership"]["state"] == "ACKED"
    assert snapshot["conflicts"]["conf-pagination-mismatch"]["state"] == "CLOSED"
    assert snapshot["operations"]["op-api-routes"]["state"] == "SUPERSEDED"
    assert snapshot["operations"]["op-api-routes-v2"]["state"] == "COMMITTED"


def _scenario_5() -> dict[str, Any]:
    driver = ScenarioDriver("sess-japan-trip-2026")
    family = [
        ("human:dad", PrincipalType.HUMAN, "David Chen", ["owner", "arbiter"], ["governance.override", "op.reject"]),
        ("human:mom", PrincipalType.HUMAN, "Wei Chen", ["owner", "arbiter"], ["governance.override", "op.reject"]),
        ("human:lily", PrincipalType.HUMAN, "Lily Chen", ["contributor"], ["intent.broadcast", "op.propose", "conflict.report"]),
        ("human:max", PrincipalType.HUMAN, "Max Chen", ["contributor"], ["intent.broadcast", "op.propose", "conflict.report"]),
        ("agent:dad-travel", PrincipalType.AGENT, "Dad Travel Agent", ["contributor"], ["intent.broadcast", "intent.update", "op.propose", "op.commit", "conflict.report"]),
        ("agent:mom-travel", PrincipalType.AGENT, "Mom Travel Agent", ["contributor"], ["intent.broadcast", "intent.update", "op.propose", "op.commit", "conflict.report"]),
        ("agent:lily-travel", PrincipalType.AGENT, "Lily Travel Agent", ["contributor"], ["intent.broadcast", "intent.update", "op.propose", "conflict.report"]),
        ("agent:max-travel", PrincipalType.AGENT, "Max Travel Agent", ["contributor"], ["intent.broadcast", "intent.update", "op.propose", "conflict.report"]),
    ]
    for principal_id, principal_type, name, roles, caps in family:
        driver.hello(principal_id, principal_type, name, roles, caps)

    announced = [
        ("agent:dad-travel", "intent-dad-culture", ["itinerary.day2.morning", "itinerary.day3.full", "itinerary.day5.full", "budget.activities"]),
        ("agent:mom-travel", "intent-mom-food", ["itinerary.day2.lunch", "itinerary.day3.evening", "itinerary.day6.evening", "budget.dining"]),
        ("agent:lily-travel", "intent-lily-shopping", ["itinerary.day4.afternoon", "itinerary.day5.afternoon", "itinerary.day5.evening", "budget.shopping", "budget.activities"]),
        ("agent:max-travel", "intent-max-anime", ["itinerary.day4.afternoon", "itinerary.day5.full", "itinerary.day6.morning", "budget.shopping", "budget.activities"]),
    ]
    for sender_id, intent_id, entities in announced:
        driver.send(
            MessageType.INTENT_ANNOUNCE,
            sender_id,
            PrincipalType.AGENT,
            IntentAnnouncePayload(intent_id=intent_id, objective=intent_id.replace("-", " "), scope=Scope(kind=ScopeKind.ENTITY_SET, entities=entities), ttl_sec=600),
        )

    driver.conflict_report(
        "agent:mom-travel",
        "conf-schedule-day5",
        ["intent-lily-shopping", "intent-max-anime"],
        [],
        "resource_contention",
        "high",
        DetectionBasisKind.RULE,
        "Lily and Max both claimed Day 5 and Day 4 afternoon.",
        "human_review",
    )
    driver.conflict_report(
        "agent:dad-travel",
        "conf-hiroshima-vs-tokyo",
        ["intent-dad-culture", "intent-lily-shopping", "intent-max-anime"],
        [],
        "semantic_goal_conflict",
        "high",
        DetectionBasisKind.MODEL_INFERENCE,
        "Dad's Hiroshima trip conflicts with Lily and Max's Tokyo plans.",
        "human_review",
    )
    driver.conflict_report(
        "agent:mom-travel",
        "conf-budget-overrun",
        ["intent-dad-culture", "intent-mom-food", "intent-lily-shopping", "intent-max-anime"],
        [],
        "resource_contention",
        "medium",
        DetectionBasisKind.HEURISTIC,
        "Combined plan exceeds the $8,000 budget.",
        "human_review",
    )
    driver.resolution(
        "human:mom",
        "conf-hiroshima-vs-tokyo",
        "res-schedule-day5",
        Decision.MERGED,
        merged=["intent-dad-culture", "intent-lily-shopping", "intent-max-anime"],
        rationale="Move Hiroshima to Day 3 and rotate Day 5 priorities.",
    )
    driver.send(
        MessageType.CONFLICT_ACK,
        "human:dad",
        PrincipalType.HUMAN,
        ConflictAckPayload(conflict_id="conf-hiroshima-vs-tokyo", ack_type="accepted"),
    )
    driver.resolution(
        "human:mom",
        "conf-schedule-day5",
        "res-schedule-siblings",
        Decision.MERGED,
        merged=["intent-lily-shopping", "intent-max-anime"],
        rationale="Resolved by the shared Day 4 and Day 5 restructure.",
    )
    driver.resolution(
        "human:dad",
        "conf-budget-overrun",
        "res-budget",
        Decision.MERGED,
        accepted=["intent-dad-culture", "intent-lily-shopping", "intent-max-anime"],
        merged=["intent-mom-food"],
        rationale="Drop the expensive omakase and keep the rest with a cheaper sushi dinner.",
    )
    updates = [
        ("agent:dad-travel", "intent-dad-culture", ["itinerary.day2.morning", "itinerary.day2.afternoon", "itinerary.day3.full", "itinerary.day6.morning", "budget.activities"]),
        ("agent:mom-travel", "intent-mom-food", ["itinerary.day2.lunch", "itinerary.day2.evening", "itinerary.day4.morning", "itinerary.day5.evening", "budget.dining"]),
        ("agent:lily-travel", "intent-lily-shopping", ["itinerary.day4.afternoon", "itinerary.day5.afternoon", "itinerary.day5.evening", "budget.shopping", "budget.activities"]),
        ("agent:max-travel", "intent-max-anime", ["itinerary.day4.morning", "itinerary.day5.morning", "itinerary.day5.afternoon", "budget.shopping", "budget.activities"]),
    ]
    for sender_id, intent_id, entities in updates:
        driver.send(
            MessageType.INTENT_UPDATE,
            sender_id,
            PrincipalType.AGENT,
            IntentUpdatePayload(intent_id=intent_id, objective=f"Updated {intent_id}", scope=Scope(kind=ScopeKind.ENTITY_SET, entities=entities), ttl_sec=600),
        )
    proposals = [
        ("agent:mom-travel", "op-kaiseki-reservation", "intent-mom-food", "bookings.dining", "booking:kaiseki-day2"),
        ("agent:lily-travel", "op-teamlab-tickets", "intent-lily-shopping", "bookings.activities", "booking:teamlab-day5"),
        ("agent:dad-travel", "op-hiroshima-tickets", "intent-dad-culture", "bookings.transport", "booking:hiroshima-day3"),
    ]
    for sender_id, op_id, intent_id, target, ref in proposals:
        driver.send(
            MessageType.OP_PROPOSE,
            sender_id,
            PrincipalType.AGENT,
            OperationPayload(op_id=op_id, intent_id=intent_id, target=target, op_kind="create", change_ref=ref, summary=op_id),
        )
    commits = [
        ("human:mom", "op-kaiseki-reservation", "intent-mom-food", "bookings.dining", "sha256:bookings-v1"),
        ("human:mom", "op-teamlab-tickets", "intent-lily-shopping", "bookings.activities", "sha256:bookings-v2"),
        ("human:dad", "op-hiroshima-tickets", "intent-dad-culture", "bookings.transport", "sha256:bookings-v3"),
        ("agent:dad-travel", "op-final-itinerary", "intent-dad-culture", "itinerary.final", "sha256:itinerary-v1"),
    ]
    before_refs = {
        "op-kaiseki-reservation": "sha256:bookings-empty",
        "op-teamlab-tickets": "sha256:bookings-v1",
        "op-hiroshima-tickets": "sha256:bookings-v2",
        "op-final-itinerary": "sha256:itinerary-empty",
    }
    for sender_id, op_id, intent_id, target, after in commits:
        sender_type = PrincipalType.HUMAN if sender_id.startswith("human:") else PrincipalType.AGENT
        driver.send(
            MessageType.OP_COMMIT,
            sender_id,
            sender_type,
            OperationPayload(
                op_id=op_id,
                intent_id=intent_id,
                target=target,
                op_kind="create",
                state_ref_before=before_refs[op_id],
                state_ref_after=after,
                change_ref=op_id,
                summary=op_id,
            ),
        )
    return driver.snapshot()


def _validate_5(snapshot: dict[str, Any]) -> None:
    assert snapshot["conflicts"]["conf-budget-overrun"]["state"] == "CLOSED"
    assert snapshot["operations"]["op-teamlab-tickets"]["state"] == "COMMITTED"
    assert snapshot["operations"]["op-final-itinerary"]["state"] == "COMMITTED"


SCENARIOS: list[ScenarioCase] = [
    ScenarioCase(
        scenario_id="scenario-1",
        title="Two AI Coding Agents Collaborate on a Microservice",
        summary="Intent-level assumption conflict about ID types gets resolved before code commits.",
        assessment="Conformant. This scenario maps cleanly to MPAC core plus governance semantics.",
        notes=[
            "The conflict is manually reported with basis.kind = model_inference, which MPAC explicitly allows.",
            "The merged outcome keeps the backend intent alive but revised, which is consistent with RESOLUTION semantics.",
        ],
        runner=_scenario_1,
        validator=_validate_1,
    ),
    ScenarioCase(
        scenario_id="scenario-2",
        title="Multi-Agent Research Paper Writing with Scope Contention",
        summary="Two agents coordinate sequential edits on the Methods section after an owner resolution.",
        assessment="Conformant. The entity_set scope and merged sequential execution fit the protocol well.",
        notes=[
            "This scenario relies on a human owner to impose ordering rather than a built-in scheduler.",
            "Both intents remain valid after resolution, which is why the outcome accepts both.",
        ],
        runner=_scenario_2,
        validator=_validate_2,
    ),
    ScenarioCase(
        scenario_id="scenario-3",
        title="Production Incident Response with Escalation",
        summary="A speculative hotfix is proposed, rejected, and redirected during a critical incident.",
        assessment="Conformant. This is a strong example of CONFLICT_ESCALATE plus governance override.",
        notes=[
            "The incident flow uses OP_PROPOSE followed by OP_REJECT, which is exactly what governance review is for.",
            "The critical conflict itself is manually inferred, not auto-detected by the reference runtime.",
        ],
        runner=_scenario_3,
        validator=_validate_3,
    ),
    ScenarioCase(
        scenario_id="scenario-4",
        title="Two Teams, Six Agents, One Codebase",
        summary="Cross-team contract ownership and later pagination mismatch are handled with structured resolutions.",
        assessment="Conformant, with one illustrative wrinkle: multiple RESOLUTION messages appear on the same conflict as a negotiation thread.",
        notes=[
            "MPAC allows conflicts to stay auditable; the spec does not forbid multiple resolutions while humans negotiate.",
            "OP_SUPERSEDE is used correctly to preserve audit history when the backend route implementation changes.",
        ],
        runner=_scenario_4,
        validator=_validate_4,
    ),
    ScenarioCase(
        scenario_id="scenario-5",
        title="Family of Four Plans a Vacation",
        summary="Family agents coordinate on schedule and budget, while parents retain final booking authority.",
        assessment="Conformant. This is a good non-software example of governance and resource contention.",
        notes=[
            "The kids' agents propose bookings while the parents commit them, matching the advertised governance roles.",
            "Budget and scheduling conflicts are reported explicitly before any irreversible bookings are finalized.",
        ],
        runner=_scenario_5,
        validator=_validate_5,
    ),
]


def run_scenario(case: ScenarioCase) -> dict[str, Any]:
    snapshot = case.runner()
    case.validator(snapshot)
    return {
        "id": case.scenario_id,
        "title": case.title,
        "summary": case.summary,
        "assessment": case.assessment,
        "notes": list(case.notes),
        "snapshot": snapshot,
    }


def run_all_scenarios() -> list[dict[str, Any]]:
    return [run_scenario(case) for case in SCENARIOS]
