"""Step-by-step guided walkthroughs for the five MPAC spec scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

from mpac.models import (
    ConflictAckPayload,
    ConflictEscalatePayload,
    Decision,
    DetectionBasisKind,
    GoodbyePayload,
    IntentAnnouncePayload,
    IntentUpdatePayload,
    IntentWithdrawPayload,
    MessageType,
    OperationPayload,
    OperationRejectPayload,
    OperationSupersedePayload,
    PrincipalType,
    Scope,
    ScopeKind,
)
from mpac.scenarios import PRESENTATIONS, SCENARIOS, ScenarioDriver

from .demo import LLMClient


Action = Callable[[ScenarioDriver], None]


@dataclass
class GuidedStep:
    step_id: str
    title: str
    operator_instruction: str
    protocol_focus: list[str]
    action: Action


@dataclass
class GuidedScenario:
    scenario_id: str
    title: str
    summary: str
    tagline: str
    actor_names: list[str]
    steps: list[GuidedStep]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "summary": self.summary,
            "tagline": self.tagline,
            "actor_names": list(self.actor_names),
            "step_count": len(self.steps),
        }


class GuidedScenarioSession:
    def __init__(self, scenario: GuidedScenario, llm: LLMClient | None = None) -> None:
        self.session_id = f"guided-{uuid4().hex[:8]}"
        self.scenario = scenario
        self.driver = ScenarioDriver(session_id=f"{scenario.scenario_id}-{uuid4().hex[:6]}", review_required=False)
        self.llm = llm
        self.current_step_index = -1
        self.history: list[dict[str, Any]] = []

    def advance(self) -> dict[str, Any]:
        if self.current_step_index + 1 >= len(self.scenario.steps):
            raise RuntimeError("Scenario is already complete.")
        before_len = len(self.driver.runtime.session.message_log)
        self.current_step_index += 1
        step = self.scenario.steps[self.current_step_index]
        step.action(self.driver)
        snapshot = self.driver.snapshot()
        message_delta = snapshot["message_log"][before_len:]
        commentary = self._make_commentary(step, message_delta, snapshot)
        event = {
            "step_index": self.current_step_index,
            "step_id": step.step_id,
            "title": step.title,
            "operator_instruction": step.operator_instruction,
            "protocol_focus": list(step.protocol_focus),
            "message_delta": message_delta,
            "commentary": commentary,
            "snapshot": snapshot,
        }
        self.history.append(event)
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "scenario": self.scenario.to_dict(),
            "current_step_index": self.current_step_index,
            "completed": self.current_step_index >= len(self.scenario.steps) - 1,
            "next_step_title": None
            if self.current_step_index + 1 >= len(self.scenario.steps)
            else self.scenario.steps[self.current_step_index + 1].title,
            "history": list(self.history),
            "snapshot": self.driver.snapshot(),
            "presentation": PRESENTATIONS[self.scenario.scenario_id],
        }

    def _make_commentary(self, step: GuidedStep, message_delta: list[dict[str, Any]], snapshot: dict[str, Any]) -> dict[str, str]:
        if self.llm is None:
            return {
                "narrator": f"{step.title}: this step moved the protocol through {', '.join(step.protocol_focus)}.",
                "operator_tip": step.operator_instruction,
                "what_changed": (
                    f"Messages this step: {len(message_delta)}. "
                    f"Intents: {len(snapshot['intents'])}. Operations: {len(snapshot['operations'])}. "
                    f"Conflicts: {len(snapshot['conflicts'])}."
                ),
            }
        prompt = (
            "Return one JSON object only.\n"
            f"Scenario: {self.scenario.title}\n"
            f"Step title: {step.title}\n"
            f"Operator instruction: {step.operator_instruction}\n"
            f"Protocol focus: {step.protocol_focus}\n"
            f"Message delta: {message_delta}\n"
            "Write a crisp walkthrough for a human learning this protocol.\n"
            "JSON schema:\n"
            "{\n"
            '  "narrator": "2-3 sentence explanation of what just happened",\n'
            '  "operator_tip": "one practical sentence telling the user what to notice",\n'
            '  "what_changed": "one sentence summarizing the state transition"\n'
            "}"
        )
        raw = self.llm.complete_json(
            system="You are a protocol coach teaching someone how MPAC works. Return valid JSON only.",
            prompt=prompt,
            temperature=0.2,
        )
        return {
            "narrator": str(raw.get("narrator") or step.operator_instruction),
            "operator_tip": str(raw.get("operator_tip") or "Watch the new messages and state transitions."),
            "what_changed": str(raw.get("what_changed") or f"{len(message_delta)} new protocol messages were added."),
        }


def _hello(d: ScenarioDriver, sender_id: str, sender_type: PrincipalType, display_name: str, roles: list[str], capabilities: list[str]) -> None:
    d.hello(sender_id, sender_type, display_name, roles, capabilities)


def _guided_scenario_1() -> GuidedScenario:
    def step1(d: ScenarioDriver) -> None:
        _hello(d, "human:maya", PrincipalType.HUMAN, "Maya Chen", ["owner", "arbiter"], ["governance.override", "conflict.report"])
        _hello(d, "agent:backend-1", PrincipalType.AGENT, "Backend Agent", ["contributor"], ["intent.broadcast", "intent.update", "op.commit", "conflict.report"])
        _hello(d, "agent:db-1", PrincipalType.AGENT, "Database Agent", ["contributor"], ["intent.broadcast", "op.commit", "conflict.report"])
        d.send(
            MessageType.INTENT_ANNOUNCE,
            "agent:backend-1",
            PrincipalType.AGENT,
            IntentAnnouncePayload(
                intent_id="intent-api-endpoint",
                objective="Create POST /api/v1/register endpoint with input validation and password hashing",
                scope=Scope(kind=ScopeKind.FILE_SET, resources=["src/routes/auth.ts", "src/validators/registration.ts", "src/services/user-service.ts"]),
                assumptions=["user.id is integer", "bcrypt is the agreed hashing algorithm"],
                ttl_sec=300,
            ),
        )
        d.send(
            MessageType.INTENT_ANNOUNCE,
            "agent:db-1",
            PrincipalType.AGENT,
            IntentAnnouncePayload(
                intent_id="intent-db-schema",
                objective="Create users table migration and add unique index on email",
                scope=Scope(kind=ScopeKind.FILE_SET, resources=["migrations/003_create_users.sql", "src/models/user.ts"]),
                assumptions=["Using PostgreSQL 15", "user.id is UUID"],
                ttl_sec=300,
            ),
        )

    def step2(d: ScenarioDriver) -> None:
        d.conflict_report(
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

    def step3(d: ScenarioDriver) -> None:
        d.resolution(
            "human:maya",
            "conf-id-type",
            "res-id-type",
            Decision.HUMAN_OVERRIDE,
            accepted=["intent-db-schema"],
            merged=["intent-api-endpoint"],
            rationale="Use UUID for all entity IDs; backend updates to UUID handling.",
        )
        d.send(
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

    def step4(d: ScenarioDriver) -> None:
        d.send(
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
        d.send(
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

    return GuidedScenario(
        scenario_id="scenario-1",
        title=SCENARIOS[0].title,
        summary=SCENARIOS[0].summary,
        tagline=PRESENTATIONS["scenario-1"]["tagline"],
        actor_names=["Backend Agent", "Database Agent", "Maya"],
        steps=[
            GuidedStep("s1-step1", "Both agents declare intent", "Click next and watch both agents expose their assumptions before code lands.", ["HELLO", "INTENT_ANNOUNCE"], step1),
            GuidedStep("s1-step2", "Conflict is reported", "Now the incompatible ID assumptions are formalized as a conflict instead of becoming a later integration bug.", ["CONFLICT_REPORT"], step2),
            GuidedStep("s1-step3", "Owner resolves and backend updates", "Notice that governance does not just pick a winner; it keeps the backend path alive but revised.", ["RESOLUTION", "INTENT_UPDATE"], step3),
            GuidedStep("s1-step4", "Compatible commits land", "With the shared contract fixed, both operations can commit safely.", ["OP_COMMIT"], step4),
        ],
    )


def _guided_scenario_2() -> GuidedScenario:
    def step1(d: ScenarioDriver) -> None:
        _hello(d, "human:dr-patel", PrincipalType.HUMAN, "Dr. Patel", ["owner"], ["governance.override"])
        _hello(d, "human:dr-liu", PrincipalType.HUMAN, "Dr. Liu", ["owner"], ["governance.override"])
        _hello(d, "agent:writer-1", PrincipalType.AGENT, "Writer Agent", ["contributor"], ["intent.broadcast", "op.commit", "conflict.report"])
        _hello(d, "agent:viz-1", PrincipalType.AGENT, "Viz Agent", ["contributor"], ["intent.broadcast", "op.commit"])
        _hello(d, "agent:cite-1", PrincipalType.AGENT, "Citation Agent", ["contributor"], ["intent.broadcast", "op.commit", "conflict.report"])
        d.send(
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
        d.send(
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

    def step2(d: ScenarioDriver) -> None:
        d.conflict_report(
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

    def step3(d: ScenarioDriver) -> None:
        d.resolution(
            "human:dr-patel",
            "conf-methods-scope",
            "res-methods-scope",
            Decision.MERGED,
            accepted=["intent-methods-draft", "intent-citations"],
            rationale="Writer drafts first, citation agent adds references after commit.",
        )

    def step4(d: ScenarioDriver) -> None:
        d.send(
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
        d.send(
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

    return GuidedScenario(
        scenario_id="scenario-2",
        title=SCENARIOS[1].title,
        summary=SCENARIOS[1].summary,
        tagline=PRESENTATIONS["scenario-2"]["tagline"],
        actor_names=["Writer Agent", "Citation Agent", "Dr. Patel"],
        steps=[
            GuidedStep("s2-step1", "Agents aim at the same section", "Start the session and watch both agents target the Methods section from different editing roles.", ["HELLO", "INTENT_ANNOUNCE"], step1),
            GuidedStep("s2-step2", "Scope overlap becomes explicit", "Advance once more to see overlap treated as protocol state instead of a hidden race.", ["CONFLICT_REPORT"], step2),
            GuidedStep("s2-step3", "Owner sets execution order", "This step shows governance creating sequence without removing either contribution.", ["RESOLUTION"], step3),
            GuidedStep("s2-step4", "Ordered commits preserve both contributions", "The second commit now builds on the first instead of overwriting it.", ["OP_COMMIT"], step4),
        ],
    )


def _guided_scenario_3() -> GuidedScenario:
    def step1(d: ScenarioDriver) -> None:
        _hello(d, "service:alertmanager", PrincipalType.SERVICE, "Alert Manager", ["observer", "contributor"], ["intent.broadcast", "conflict.report"])
        _hello(d, "human:jordan", PrincipalType.HUMAN, "Jordan", ["arbiter"], ["governance.override", "op.reject"])
        _hello(d, "agent:diag-1", PrincipalType.AGENT, "Diagnostics Agent", ["contributor"], ["intent.broadcast", "conflict.report"])
        _hello(d, "agent:hotfix-1", PrincipalType.AGENT, "Hotfix Agent", ["contributor"], ["intent.broadcast", "op.propose"])
        d.send(
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
        d.send(
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
        d.send(
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

    def step2(d: ScenarioDriver) -> None:
        d.conflict_report(
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
        d.send(
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

    def step3(d: ScenarioDriver) -> None:
        d.send(
            MessageType.OP_REJECT,
            "human:jordan",
            PrincipalType.HUMAN,
            OperationRejectPayload(
                op_id="op-cache-flush",
                reason="Wrong root cause. Payment gateway is returning 502s.",
            ),
        )
        d.resolution(
            "human:jordan",
            "conf-wrong-root-cause",
            "res-root-cause",
            Decision.HUMAN_OVERRIDE,
            accepted=["intent-diagnose"],
            rejected=["intent-hotfix-cache"],
            rationale="Continue diagnosis and pivot hotfix agent to payment gateway investigation.",
        )

    def step4(d: ScenarioDriver) -> None:
        d.send(
            MessageType.INTENT_WITHDRAW,
            "agent:hotfix-1",
            PrincipalType.AGENT,
            IntentWithdrawPayload(intent_id="intent-hotfix-cache", reason="rejected_by_arbiter"),
        )
        d.send(
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

    return GuidedScenario(
        scenario_id="scenario-3",
        title=SCENARIOS[2].title,
        summary=SCENARIOS[2].summary,
        tagline=PRESENTATIONS["scenario-3"]["tagline"],
        actor_names=["Diagnostics Agent", "Hotfix Agent", "Jordan"],
        steps=[
            GuidedStep("s3-step1", "Investigation and speculative fix diverge", "Start by watching one agent investigate while the other only proposes a production action.", ["HELLO", "INTENT_ANNOUNCE", "OP_PROPOSE"], step1),
            GuidedStep("s3-step2", "Critical conflict escalates", "This step shows why proposal and commit are separate: risky action is still stoppable.", ["CONFLICT_REPORT", "CONFLICT_ESCALATE"], step2),
            GuidedStep("s3-step3", "Human rejects the wrong fix", "Governance now rejects the proposed operation and resolves the conflict in favor of diagnosis.", ["OP_REJECT", "RESOLUTION"], step3),
            GuidedStep("s3-step4", "The losing agent pivots into useful work", "The protocol does not dead-end the hotfix agent; it redirects it into a safer new intent.", ["INTENT_WITHDRAW", "INTENT_ANNOUNCE"], step4),
        ],
    )


def _guided_scenario_4() -> GuidedScenario:
    def step1(d: ScenarioDriver) -> None:
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
            _hello(d, principal_id, principal_type, display_name, roles, caps)
        intents = [
            ("agent:bob-db", "intent-db-tables", Scope(kind=ScopeKind.FILE_SET, resources=["migrations/010_dashboard_tables.sql", "src/models/dashboard.py"])),
            ("agent:bob-api", "intent-api-endpoints", Scope(kind=ScopeKind.FILE_SET, resources=["src/routes/dashboard.py", "src/services/dashboard_service.py", "api/dashboard.openapi.yaml"])),
            ("agent:bob-test", "intent-backend-tests", Scope(kind=ScopeKind.FILE_SET, resources=["tests/integration/test_dashboard_api.py"])),
            ("agent:alice-ui", "intent-ui-components", Scope(kind=ScopeKind.FILE_SET, resources=["src/components/Dashboard/DashboardGrid.tsx"])),
            ("agent:alice-state", "intent-state-management", Scope(kind=ScopeKind.FILE_SET, resources=["src/store/dashboardSlice.ts", "src/hooks/useDashboard.ts", "api/dashboard.openapi.yaml"])),
            ("agent:alice-test", "intent-frontend-tests", Scope(kind=ScopeKind.FILE_SET, resources=["src/components/Dashboard/__tests__/DashboardGrid.test.tsx"])),
        ]
        for sender_id, intent_id, scope in intents:
            d.send(
                MessageType.INTENT_ANNOUNCE,
                sender_id,
                PrincipalType.AGENT,
                IntentAnnouncePayload(intent_id=intent_id, objective=intent_id.replace("-", " "), scope=scope, ttl_sec=600),
            )

    def step2(d: ScenarioDriver) -> None:
        d.conflict_report(
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

    def step3(d: ScenarioDriver) -> None:
        d.resolution(
            "human:bob",
            "conf-openapi-ownership",
            "res-openapi-v1",
            Decision.MERGED,
            accepted=["intent-api-endpoints"],
            merged=["intent-state-management"],
            rationale="Bob API writes spec first; Alice state consumes it.",
        )
        d.send(
            MessageType.CONFLICT_ACK,
            "agent:alice-state",
            PrincipalType.AGENT,
            ConflictAckPayload(conflict_id="conf-openapi-ownership", ack_type="disputed"),
        )
        d.resolution(
            "human:alice",
            "conf-openapi-ownership",
            "res-openapi-v2",
            Decision.MERGED,
            accepted=["intent-api-endpoints", "intent-state-management"],
            rationale="Sequential shared writes to the OpenAPI spec are allowed.",
        )
        d.send(
            MessageType.CONFLICT_ACK,
            "human:bob",
            PrincipalType.HUMAN,
            ConflictAckPayload(conflict_id="conf-openapi-ownership", ack_type="accepted"),
        )

    def step4(d: ScenarioDriver) -> None:
        commits = [
            ("agent:bob-db", "op-db-migration", "intent-db-tables", "migrations/010_dashboard_tables.sql", "sha256:db-mig-v1"),
            ("agent:bob-api", "op-api-openapi", "intent-api-endpoints", "api/dashboard.openapi.yaml", "sha256:openapi-v1"),
            ("agent:bob-api", "op-api-routes", "intent-api-endpoints", "src/routes/dashboard.py", "sha256:routes-v1"),
            ("agent:alice-ui", "op-ui-components", "intent-ui-components", "src/components/Dashboard/DashboardGrid.tsx", "sha256:grid-v1"),
            ("agent:alice-state", "op-state-slice", "intent-state-management", "src/store/dashboardSlice.ts", "sha256:slice-v1"),
            ("agent:alice-state", "op-openapi-extensions", "intent-state-management", "api/dashboard.openapi.yaml", "sha256:openapi-v2"),
        ]
        for sender_id, op_id, intent_id, target, after in commits:
            d.send(
                MessageType.OP_COMMIT,
                sender_id,
                PrincipalType.AGENT,
                OperationPayload(
                    op_id=op_id,
                    intent_id=intent_id,
                    target=target,
                    op_kind="create",
                    state_ref_before="sha256:empty",
                    state_ref_after=after,
                    change_ref=f"{op_id}-diff",
                    summary=op_id,
                ),
            )
        d.conflict_report(
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

    def step5(d: ScenarioDriver) -> None:
        d.resolution(
            "human:bob",
            "conf-pagination-mismatch",
            "res-pagination",
            Decision.HUMAN_OVERRIDE,
            merged=["intent-api-endpoints", "intent-state-management"],
            rationale="Spec is correct; backend routes must be fixed to cursor pagination.",
        )
        d.send(
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
        d.send(
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
        d.send(
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
        d.send(
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
        d.send(
            MessageType.GOODBYE,
            "agent:bob-test",
            PrincipalType.AGENT,
            GoodbyePayload(reason="session_complete", active_intents=[], intent_disposition="withdraw"),
        )

    return GuidedScenario(
        scenario_id="scenario-4",
        title=SCENARIOS[3].title,
        summary=SCENARIOS[3].summary,
        tagline=PRESENTATIONS["scenario-4"]["tagline"],
        actor_names=["Alice Team", "Bob Team", "Shared Contract"],
        steps=[
            GuidedStep("s4-step1", "Six agents fan out", "Start the session and inspect how healthy parallelism coexists with one dangerous shared boundary.", ["HELLO", "INTENT_ANNOUNCE"], step1),
            GuidedStep("s4-step2", "Shared contract conflict is raised", "The OpenAPI file is the cross-team boundary; now it becomes a tracked protocol object.", ["CONFLICT_REPORT"], step2),
            GuidedStep("s4-step3", "Humans negotiate a visible boundary agreement", "Step through the back-and-forth resolution thread and notice that negotiation itself becomes auditable.", ["RESOLUTION", "CONFLICT_ACK"], step3),
            GuidedStep("s4-step4", "Work lands and drift is detected", "Advance to see both teams commit work, then watch a test agent catch spec drift as another conflict.", ["OP_COMMIT", "CONFLICT_REPORT"], step4),
            GuidedStep("s4-step5", "Bad route history is preserved and replaced", "The route fix supersedes the wrong operation instead of erasing it, keeping the audit trail intact.", ["RESOLUTION", "OP_SUPERSEDE", "OP_COMMIT", "GOODBYE"], step5),
        ],
    )


def _guided_scenario_5() -> GuidedScenario:
    def step1(d: ScenarioDriver) -> None:
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
            _hello(d, principal_id, principal_type, name, roles, caps)
        announced = [
            ("agent:dad-travel", "intent-dad-culture", ["itinerary.day2.morning", "itinerary.day3.full", "itinerary.day5.full", "budget.activities"]),
            ("agent:mom-travel", "intent-mom-food", ["itinerary.day2.lunch", "itinerary.day3.evening", "itinerary.day6.evening", "budget.dining"]),
            ("agent:lily-travel", "intent-lily-shopping", ["itinerary.day4.afternoon", "itinerary.day5.afternoon", "itinerary.day5.evening", "budget.shopping", "budget.activities"]),
            ("agent:max-travel", "intent-max-anime", ["itinerary.day4.afternoon", "itinerary.day5.full", "itinerary.day6.morning", "budget.shopping", "budget.activities"]),
        ]
        for sender_id, intent_id, entities in announced:
            d.send(
                MessageType.INTENT_ANNOUNCE,
                sender_id,
                PrincipalType.AGENT,
                IntentAnnouncePayload(intent_id=intent_id, objective=intent_id.replace("-", " "), scope=Scope(kind=ScopeKind.ENTITY_SET, entities=entities), ttl_sec=600),
            )

    def step2(d: ScenarioDriver) -> None:
        d.conflict_report(
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
        d.conflict_report(
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
        d.conflict_report(
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

    def step3(d: ScenarioDriver) -> None:
        d.resolution(
            "human:mom",
            "conf-hiroshima-vs-tokyo",
            "res-schedule-day5",
            Decision.MERGED,
            merged=["intent-dad-culture", "intent-lily-shopping", "intent-max-anime"],
            rationale="Move Hiroshima to Day 3 and rotate Day 5 priorities.",
        )
        d.send(
            MessageType.CONFLICT_ACK,
            "human:dad",
            PrincipalType.HUMAN,
            ConflictAckPayload(conflict_id="conf-hiroshima-vs-tokyo", ack_type="accepted"),
        )
        d.resolution(
            "human:mom",
            "conf-schedule-day5",
            "res-schedule-siblings",
            Decision.MERGED,
            merged=["intent-lily-shopping", "intent-max-anime"],
            rationale="Resolved by the shared Day 4 and Day 5 restructure.",
        )
        d.resolution(
            "human:dad",
            "conf-budget-overrun",
            "res-budget",
            Decision.MERGED,
            accepted=["intent-dad-culture", "intent-lily-shopping", "intent-max-anime"],
            merged=["intent-mom-food"],
            rationale="Drop the expensive omakase and keep the rest with a cheaper sushi dinner.",
        )

    def step4(d: ScenarioDriver) -> None:
        updates = [
            ("agent:dad-travel", "intent-dad-culture", ["itinerary.day2.morning", "itinerary.day2.afternoon", "itinerary.day3.full", "itinerary.day6.morning", "budget.activities"]),
            ("agent:mom-travel", "intent-mom-food", ["itinerary.day2.lunch", "itinerary.day2.evening", "itinerary.day4.morning", "itinerary.day5.evening", "budget.dining"]),
            ("agent:lily-travel", "intent-lily-shopping", ["itinerary.day4.afternoon", "itinerary.day5.afternoon", "itinerary.day5.evening", "budget.shopping", "budget.activities"]),
            ("agent:max-travel", "intent-max-anime", ["itinerary.day4.morning", "itinerary.day5.morning", "itinerary.day5.afternoon", "budget.shopping", "budget.activities"]),
        ]
        for sender_id, intent_id, entities in updates:
            d.send(
                MessageType.INTENT_UPDATE,
                sender_id,
                PrincipalType.AGENT,
                IntentUpdatePayload(intent_id=intent_id, objective=f"Updated {intent_id}", scope=Scope(kind=ScopeKind.ENTITY_SET, entities=entities), ttl_sec=600),
            )

    def step5(d: ScenarioDriver) -> None:
        proposals = [
            ("agent:mom-travel", "op-kaiseki-reservation", "intent-mom-food", "bookings.dining", "booking:kaiseki-day2"),
            ("agent:lily-travel", "op-teamlab-tickets", "intent-lily-shopping", "bookings.activities", "booking:teamlab-day5"),
            ("agent:dad-travel", "op-hiroshima-tickets", "intent-dad-culture", "bookings.transport", "booking:hiroshima-day3"),
        ]
        for sender_id, op_id, intent_id, target, ref in proposals:
            d.send(
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
            d.send(
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

    return GuidedScenario(
        scenario_id="scenario-5",
        title=SCENARIOS[4].title,
        summary=SCENARIOS[4].summary,
        tagline=PRESENTATIONS["scenario-5"]["tagline"],
        actor_names=["Parents", "Kids' Agents", "Travel Agents"],
        steps=[
            GuidedStep("s5-step1", "Family priorities are announced", "Start by watching multiple principals express overlapping preferences before anyone spends money.", ["HELLO", "INTENT_ANNOUNCE"], step1),
            GuidedStep("s5-step2", "Schedule and budget conflicts surface", "Advance to make the hidden family tradeoffs visible as protocol conflicts.", ["CONFLICT_REPORT"], step2),
            GuidedStep("s5-step3", "Parents resolve the tradeoffs", "Notice how owner authority keeps the kids' preferences in view while still making a final call.", ["RESOLUTION", "CONFLICT_ACK"], step3),
            GuidedStep("s5-step4", "Agents revise to the agreed plan", "This step shows coordination after governance: intents are updated instead of silently drifting.", ["INTENT_UPDATE"], step4),
            GuidedStep("s5-step5", "Proposal and commit authority are separated", "The family can let agents suggest bookings while parents retain the right to finalize them.", ["OP_PROPOSE", "OP_COMMIT"], step5),
        ],
    )


GUIDED_SCENARIOS: dict[str, GuidedScenario] = {
    item.scenario_id: item
    for item in [
        _guided_scenario_1(),
        _guided_scenario_2(),
        _guided_scenario_3(),
        _guided_scenario_4(),
        _guided_scenario_5(),
    ]
}


def list_guided_scenarios() -> list[dict[str, Any]]:
    return [scenario.to_dict() for scenario in GUIDED_SCENARIOS.values()]


def create_guided_session(scenario_id: str, llm: LLMClient | None = None) -> GuidedScenarioSession:
    scenario = GUIDED_SCENARIOS.get(scenario_id)
    if scenario is None:
        raise KeyError(f"Unknown scenario_id: {scenario_id}")
    return GuidedScenarioSession(scenario, llm=llm)
