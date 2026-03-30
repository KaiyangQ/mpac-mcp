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


PRESENTATIONS: dict[str, dict[str, Any]] = {
    "scenario-1": {
        "tagline": "Two coding agents are building the same registration feature from different sides.",
        "shared_object": {
            "title": "Shared Work",
            "kind": "code",
            "label": "Registration flow and user identity contract",
            "before": "POST /register\n- backend assumes user.id: int\n- db schema not finalized\n- no shared contract yet",
            "after": "POST /register\n- backend uses user.id: UUID string\n- db schema uses UUID primary key\n- route and migration are compatible",
        },
        "actors": [
            {"name": "Backend Agent", "role": "Writes route and service code", "color": "agent-a"},
            {"name": "Database Agent", "role": "Designs schema and migration", "color": "agent-b"},
            {"name": "Maya", "role": "Human owner and arbiter", "color": "owner"},
        ],
        "steps": [
            {
                "title": "Both Agents Start Working",
                "focus": "shared",
                "summary": "The backend agent plans the registration endpoint while the database agent plans the user schema.",
                "left_title": "Backend Agent",
                "left_body": "I am implementing POST /register and I currently assume user IDs behave like integers in the service layer.",
                "right_title": "Database Agent",
                "right_body": "I am creating the users table and I want UUID primary keys so the system stays consistent with company standards.",
                "status": ["Both plans are visible before code is committed", "Shared feature boundary: registration"],
                "protocol": ["INTENT_ANNOUNCE", "INTENT_ANNOUNCE"],
            },
            {
                "title": "The Conflict Becomes Visible",
                "focus": "conflict",
                "summary": "The problem is not a merge conflict yet. It is a design mismatch: integer IDs versus UUIDs.",
                "left_title": "What Would Go Wrong",
                "left_body": "Without coordination, both agents could commit code that looks valid locally but breaks when the route and schema meet.",
                "right_title": "What MPAC Sees",
                "right_body": "The assumptions are incompatible, so the conflict is raised before incompatible code lands.",
                "status": ["Conflict category: assumption contradiction", "Severity: high"],
                "protocol": ["CONFLICT_REPORT"],
            },
            {
                "title": "Governance Decides",
                "focus": "governance",
                "summary": "Maya resolves the issue by choosing UUID as the shared contract for both agents.",
                "left_title": "Owner Decision",
                "left_body": "Use UUID everywhere. The database plan stays. The backend agent must revise its assumptions and continue.",
                "right_title": "Why This Matters",
                "right_body": "The agents do not need to guess who wins. Governance makes the decision explicit and attributable.",
                "status": ["Winner: UUID-based schema", "Backend plan stays active but must be revised"],
                "protocol": ["RESOLUTION", "INTENT_UPDATE"],
            },
            {
                "title": "Both Sides Commit Safely",
                "focus": "outcome",
                "summary": "The database agent commits the migration, and the backend agent commits an endpoint that now matches the schema.",
                "left_title": "Database Commit",
                "left_body": "Create users table with UUID primary key.",
                "right_title": "Backend Commit",
                "right_body": "Create register endpoint that treats user.id as a UUID string.",
                "status": ["No incompatible commit reached shared state", "Final outcome: route and schema agree"],
                "protocol": ["OP_COMMIT", "OP_COMMIT"],
            },
        ],
        "outcome": {
            "title": "Why MPAC Helped",
            "bullets": [
                "The agents exposed their plans before writing conflicting code.",
                "The conflict was resolved at the design layer, not after a broken integration.",
                "The final code path is compatible because the protocol forced coordination first.",
            ],
        },
    },
    "scenario-2": {
        "tagline": "Two writing-related agents both want to touch the Methods section of a paper.",
        "shared_object": {
            "title": "Shared Work",
            "kind": "document",
            "label": "Paper Methods section",
            "before": "Methods section is empty.\nWriter wants to draft it.\nCitation agent wants to edit it too.",
            "after": "Writer drafts Methods first.\nCitation agent adds references afterward.\nFinal section is complete and cited.",
        },
        "actors": [
            {"name": "Writer Agent", "role": "Drafts section text", "color": "agent-a"},
            {"name": "Citation Agent", "role": "Adds references", "color": "agent-b"},
            {"name": "Dr. Patel", "role": "Section owner", "color": "owner"},
        ],
        "steps": [
            {
                "title": "Both Agents Aim at the Same Section",
                "focus": "shared",
                "summary": "The writer wants to draft Methods and the citation agent wants to edit Methods too.",
                "left_title": "Writer Agent",
                "left_body": "I want to produce the full Methods narrative.",
                "right_title": "Citation Agent",
                "right_body": "I want to insert references into Methods and update the bibliography.",
                "status": ["Shared section: Methods", "Risk: concurrent edits"],
                "protocol": ["INTENT_ANNOUNCE", "INTENT_ANNOUNCE"],
            },
            {
                "title": "MPAC Turns Overlap into an Explicit Conflict",
                "focus": "conflict",
                "summary": "Instead of quietly racing to edit the same section, the overlap becomes visible.",
                "left_title": "The Real Problem",
                "left_body": "If both agents edit Methods at once, one can easily overwrite the other's paragraphs.",
                "right_title": "Protocol Effect",
                "right_body": "The overlap is elevated into a conflict report so someone can decide execution order.",
                "status": ["Conflict category: scope overlap", "Suggested action: sequential execution"],
                "protocol": ["CONFLICT_REPORT"],
            },
            {
                "title": "The Owner Chooses a Safe Sequence",
                "focus": "governance",
                "summary": "Dr. Patel allows both agents to continue, but only in order.",
                "left_title": "Resolution",
                "left_body": "Writer drafts first. Citation agent waits until the text exists, then edits the updated version.",
                "right_title": "Result",
                "right_body": "No one loses ownership of the work. They just stop colliding.",
                "status": ["Both intents accepted", "Execution order is explicit"],
                "protocol": ["RESOLUTION"],
            },
            {
                "title": "The Paper Improves in Two Passes",
                "focus": "outcome",
                "summary": "The writer commits the Methods text, then the citation agent safely enriches the finished section.",
                "left_title": "Pass 1",
                "left_body": "Methods draft is written.",
                "right_title": "Pass 2",
                "right_body": "Citations are inserted into the exact text that now exists.",
                "status": ["Final section is ordered and complete", "No accidental overwrite"],
                "protocol": ["OP_COMMIT", "OP_COMMIT"],
            },
        ],
        "outcome": {
            "title": "Why MPAC Helped",
            "bullets": [
                "The overlap was surfaced before simultaneous edits damaged the paper.",
                "Governance added ordering without requiring a custom scheduler.",
                "The final document kept contributions from both agents.",
            ],
        },
    },
    "scenario-3": {
        "tagline": "One incident agent wants to apply a fast fix while another sees evidence the fix is wrong.",
        "shared_object": {
            "title": "Shared Work",
            "kind": "incident",
            "label": "Checkout outage response",
            "before": "Hotfix agent proposes cache flush.\nDiagnostics suspect payment gateway 502s.\nRisk of wrong action in production.",
            "after": "Speculative cache fix is rejected.\nDiagnostics continue.\nHotfix agent pivots to gateway investigation.",
        },
        "actors": [
            {"name": "Diagnostics Agent", "role": "Investigates root cause", "color": "agent-a"},
            {"name": "Hotfix Agent", "role": "Proposes immediate remediation", "color": "agent-b"},
            {"name": "Jordan", "role": "Human SRE arbiter", "color": "owner"},
        ],
        "steps": [
            {
                "title": "Two Agents React Differently",
                "focus": "shared",
                "summary": "One agent investigates, while the other jumps ahead with a familiar-looking fix.",
                "left_title": "Diagnostics Agent",
                "left_body": "I am checking logs, traces, and metrics before changing production.",
                "right_title": "Hotfix Agent",
                "right_body": "I want to flush checkout cache right now because this resembles a past incident.",
                "status": ["Hotfix is only proposed, not executed", "The incident is still under review"],
                "protocol": ["INTENT_ANNOUNCE", "OP_PROPOSE"],
            },
            {
                "title": "MPAC Makes the Risk Explicit",
                "focus": "conflict",
                "summary": "Diagnostics find evidence that the hotfix is pointed at the wrong root cause.",
                "left_title": "Danger Without Coordination",
                "left_body": "A wrong production fix can waste time, hide the actual issue, and make the outage worse.",
                "right_title": "Protocol Response",
                "right_body": "The contradiction is raised as a critical conflict and escalated to the human arbiter.",
                "status": ["Conflict severity: critical", "Escalated to SRE"],
                "protocol": ["CONFLICT_REPORT", "CONFLICT_ESCALATE"],
            },
            {
                "title": "The Arbiter Stops the Wrong Fix",
                "focus": "governance",
                "summary": "Jordan rejects the proposed cache flush and resolves the conflict in favor of further diagnosis.",
                "left_title": "Human Decision",
                "left_body": "Do not execute the cache flush. Continue investigation and pivot toward the payment gateway.",
                "right_title": "Governance Effect",
                "right_body": "The speculative action is formally rejected instead of silently ignored or accidentally applied.",
                "status": ["Proposed fix rejected", "Root-cause investigation remains active"],
                "protocol": ["OP_REJECT", "RESOLUTION"],
            },
            {
                "title": "The Agents Re-align and Continue",
                "focus": "outcome",
                "summary": "The hotfix agent withdraws its old plan and starts investigating the real failure domain.",
                "left_title": "Old Path",
                "left_body": "Cache-flush plan is withdrawn.",
                "right_title": "New Path",
                "right_body": "A new intent begins around payment gateway connectivity.",
                "status": ["Production stayed safer", "Recovery work continues with better alignment"],
                "protocol": ["INTENT_WITHDRAW", "INTENT_ANNOUNCE"],
            },
        ],
        "outcome": {
            "title": "Why MPAC Helped",
            "bullets": [
                "A risky production action was intercepted before execution.",
                "Escalation gave the SRE enough context to make a fast decision.",
                "The losing agent did not just stop; it pivoted into useful work.",
            ],
        },
    },
    "scenario-4": {
        "tagline": "Two teams with six agents share one codebase and one fragile API boundary.",
        "shared_object": {
            "title": "Shared Work",
            "kind": "code",
            "label": "Dashboard feature across frontend, backend, and shared API contract",
            "before": "Frontend and backend agents both want to touch api/dashboard.openapi.yaml.\nLater, the implementation drifts from the spec.",
            "after": "Contract ownership is sequenced, routes are superseded cleanly, and both test agents validate the final version.",
        },
        "actors": [
            {"name": "Alice Team", "role": "Frontend owner plus UI, state, and test agents", "color": "agent-a"},
            {"name": "Bob Team", "role": "Backend owner plus API, DB, and test agents", "color": "agent-b"},
            {"name": "Shared Contract", "role": "OpenAPI file both teams depend on", "color": "shared"},
        ],
        "steps": [
            {
                "title": "Parallel Work Starts Across Two Teams",
                "focus": "shared",
                "summary": "Six agents fan out across database, API, UI, state, and tests.",
                "left_title": "Backend Team",
                "left_body": "Database and API agents move on schema and endpoints.",
                "right_title": "Frontend Team",
                "right_body": "UI and state agents prepare components and client-side integration.",
                "status": ["Parallelism is good", "Shared API contract is a risky boundary"],
                "protocol": ["INTENT_ANNOUNCE", "INTENT_ANNOUNCE", "INTENT_ANNOUNCE"],
            },
            {
                "title": "Both Teams Reach for the Same Boundary File",
                "focus": "conflict",
                "summary": "The frontend state agent and backend API agent both need the shared OpenAPI spec.",
                "left_title": "Why This Hurts",
                "left_body": "If both sides edit the contract at once, each team can leave with a different understanding of the API.",
                "right_title": "What MPAC Changes",
                "right_body": "The contract conflict becomes a first-class object before either side silently diverges.",
                "status": ["Conflict category: scope overlap", "Cross-team coordination required"],
                "protocol": ["CONFLICT_REPORT"],
            },
            {
                "title": "Humans Negotiate the Boundary",
                "focus": "governance",
                "summary": "Bob proposes one ownership model, Alice pushes back, and they converge on sequential shared writes.",
                "left_title": "Negotiation",
                "left_body": "Backend writes the core spec first. Frontend then adds its extensions afterward.",
                "right_title": "Protocol Benefit",
                "right_body": "This is not a hidden Slack agreement. It becomes explicit, attributable, and visible to every agent.",
                "status": ["Negotiated resolution", "Shared boundary gets an execution order"],
                "protocol": ["RESOLUTION", "CONFLICT_ACK", "RESOLUTION", "CONFLICT_ACK"],
            },
            {
                "title": "A Second Problem Appears Later",
                "focus": "conflict",
                "summary": "The backend implementation drifts from the agreed spec, and a test agent catches it.",
                "left_title": "Mismatch",
                "left_body": "Routes use offset pagination while the spec and frontend expect cursor pagination.",
                "right_title": "Recovery",
                "right_body": "Instead of losing the history, the wrong route commit is explicitly superseded and replaced.",
                "status": ["Cross-team bug detected", "Old operation preserved for audit"],
                "protocol": ["CONFLICT_REPORT", "RESOLUTION", "OP_SUPERSEDE", "OP_COMMIT"],
            },
            {
                "title": "The System Stabilizes",
                "focus": "outcome",
                "summary": "Once the shared boundary is settled, both teams' tests run against the corrected contract.",
                "left_title": "Backend Tests",
                "left_body": "Integration tests confirm routes and pagination behavior.",
                "right_title": "Frontend Tests",
                "right_body": "Component and hook tests confirm the client matches the contract.",
                "status": ["Final contract is aligned", "Both teams can trust the same shared state"],
                "protocol": ["OP_COMMIT", "OP_COMMIT", "GOODBYE"],
            },
        ],
        "outcome": {
            "title": "Why MPAC Helped",
            "bullets": [
                "It gave two teams a structured way to negotiate one shared boundary file.",
                "It preserved an audit trail when the backend implementation had to be corrected.",
                "It let test agents surface cross-team breakage early enough to recover cleanly.",
            ],
        },
    },
    "scenario-5": {
        "tagline": "Four travel agents plan one trip, but time, budget, and family priorities all collide.",
        "shared_object": {
            "title": "Shared Work",
            "kind": "planner",
            "label": "Family trip itinerary, budget, and bookings",
            "before": "Everyone has different goals for the same days and the same money.\nNo bookings are finalized yet.",
            "after": "The family gets one coherent itinerary with approved bookings and a budget-conscious compromise.",
        },
        "actors": [
            {"name": "Parents", "role": "Owners and final decision-makers", "color": "owner"},
            {"name": "Kids' Agents", "role": "Propose shopping and anime activities", "color": "agent-a"},
            {"name": "Travel Agents", "role": "Propose dining, transport, and itinerary bookings", "color": "agent-b"},
        ],
        "steps": [
            {
                "title": "Everyone Brings Their Own Priorities",
                "focus": "shared",
                "summary": "Dad wants culture, Mom wants food, Lily wants shopping, and Max wants anime and gaming.",
                "left_title": "What Makes This Hard",
                "left_body": "The same trip days and the same household budget must satisfy four different people.",
                "right_title": "Why Agents Help",
                "right_body": "Each person can explore ideas through their own agent without immediately committing the whole family.",
                "status": ["Four overlapping plans", "No bookings committed yet"],
                "protocol": ["INTENT_ANNOUNCE", "INTENT_ANNOUNCE", "INTENT_ANNOUNCE", "INTENT_ANNOUNCE"],
            },
            {
                "title": "Conflicts Surface Before Anyone Books Anything",
                "focus": "conflict",
                "summary": "The agents uncover schedule collisions and a budget overrun across the whole plan.",
                "left_title": "Schedule Conflicts",
                "left_body": "Day 5 cannot be both Hiroshima and Tokyo. Lily and Max also want overlapping time blocks.",
                "right_title": "Budget Conflict",
                "right_body": "Taken together, the family's plans exceed the target budget.",
                "status": ["Time contention", "Budget contention"],
                "protocol": ["CONFLICT_REPORT", "CONFLICT_REPORT", "CONFLICT_REPORT"],
            },
            {
                "title": "Parents Resolve the Family Tradeoffs",
                "focus": "governance",
                "summary": "The parents merge everyone's priorities into a compromise itinerary and trim one expensive dinner.",
                "left_title": "Schedule Resolution",
                "left_body": "They restructure Day 4 and Day 5 so both kids still get their priorities and Hiroshima moves to a different day.",
                "right_title": "Budget Resolution",
                "right_body": "They keep the important experiences but replace the expensive omakase dinner with a cheaper option.",
                "status": ["Conflicts resolved by owners", "Compromise keeps most intents alive"],
                "protocol": ["RESOLUTION", "CONFLICT_ACK", "RESOLUTION", "RESOLUTION"],
            },
            {
                "title": "Agents Update the Plan",
                "focus": "outcome",
                "summary": "Each travel agent revises its intent to match the agreed schedule and budget.",
                "left_title": "What Changes",
                "left_body": "Dates move, activities are re-ordered, and the dining budget drops.",
                "right_title": "Why It Matters",
                "right_body": "The family now has aligned plans before any non-refundable booking is made.",
                "status": ["Revised intents are aligned", "Booking stage can begin safely"],
                "protocol": ["INTENT_UPDATE", "INTENT_UPDATE", "INTENT_UPDATE", "INTENT_UPDATE"],
            },
            {
                "title": "Proposals Become Approved Bookings",
                "focus": "outcome",
                "summary": "Agents propose reservations, but only the parents commit them.",
                "left_title": "Governance in Practice",
                "left_body": "The kids' agents can suggest tickets, but they cannot spend the family budget on their own.",
                "right_title": "Final Result",
                "right_body": "Parents approve the bookings and the final itinerary is committed once everything is coherent.",
                "status": ["Proposal power and commit power are separated", "Final plan is executable"],
                "protocol": ["OP_PROPOSE", "OP_COMMIT", "OP_COMMIT", "OP_COMMIT"],
            },
        ],
        "outcome": {
            "title": "Why MPAC Helped",
            "bullets": [
                "The family caught schedule and budget conflicts before buying tickets.",
                "Parents stayed in control of final commitments without silencing the kids' preferences.",
                "The final itinerary emerged from structured coordination, not chaos.",
            ],
        },
    },
}


def run_scenario(case: ScenarioCase) -> dict[str, Any]:
    snapshot = case.runner()
    case.validator(snapshot)
    return {
        "id": case.scenario_id,
        "title": case.title,
        "summary": case.summary,
        "assessment": case.assessment,
        "notes": list(case.notes),
        "presentation": PRESENTATIONS[case.scenario_id],
        "snapshot": snapshot,
    }


def run_all_scenarios() -> list[dict[str, Any]]:
    return [run_scenario(case) for case in SCENARIOS]
