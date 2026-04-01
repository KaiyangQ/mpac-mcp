"""Interactive coordination demo using the MPAC runtime and an LLM."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from mpac.models import (
    Decision,
    HeartbeatPayload,
    HelloPayload,
    IntentAnnouncePayload,
    MessageType,
    OperationPayload,
    Outcome,
    PrincipalType,
    ResolutionPayload,
    Role,
    Scope,
    ScopeKind,
)
from mpac.runtime.engine import MPACRuntime


class LLMClient(Protocol):
    def complete_json(self, *, system: str, prompt: str, temperature: float = 0.2) -> dict[str, Any]:
        ...


@dataclass
class DemoConfig:
    model: str | None = None
    human_id: str = "human:operator"
    human_name: str = "Local Operator"
    agent_specs: list[dict[str, str]] = field(
        default_factory=lambda: [
            {
                "id": "agent:builder",
                "name": "Builder Agent",
                "style": "Bias toward a concrete implementation plan that moves work forward quickly.",
            },
            {
                "id": "agent:reviewer",
                "name": "Reviewer Agent",
                "style": "Bias toward risk discovery, safer rollouts, and identifying hidden coupling.",
            },
        ]
    )


@dataclass
class ResolutionSuggestion:
    conflict_id: str
    accepted_ids: list[str]
    rejected_ids: list[str]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "accepted_ids": list(self.accepted_ids),
            "rejected_ids": list(self.rejected_ids),
            "rationale": self.rationale,
        }


class CoordinationDemo:
    """A thin orchestration layer around the MPAC runtime for browser demos."""

    def __init__(self, llm: LLMClient, config: DemoConfig | None = None) -> None:
        self.llm = llm
        self.config = config or DemoConfig()
        self.runtime = MPACRuntime()
        self._hello(
            self.config.human_id,
            self.config.human_name,
            PrincipalType.HUMAN,
            [Role.OWNER.value, Role.REVIEWER.value],
            ["intent.broadcast", "op.propose", "op.commit", "governance.override"],
        )
        for spec in self.config.agent_specs:
            self._hello(
                spec["id"],
                spec["name"],
                PrincipalType.AGENT,
                [Role.CONTRIBUTOR.value],
                ["intent.broadcast", "op.propose", "op.commit"],
            )

    @property
    def session_id(self) -> str:
        return self.runtime.session.session_id

    def run_round(self, *, task: str, shared_targets: list[str]) -> dict[str, Any]:
        shared_targets = [target.strip() for target in shared_targets if target.strip()]
        if not shared_targets:
            shared_targets = ["workspace/shared-artifact.md"]

        plans: list[dict[str, Any]] = []
        for spec in self.config.agent_specs:
            plan = self._ask_agent_for_plan(spec, task, shared_targets)
            plans.append(plan)
            self._send_heartbeat(spec["id"], plan.get("intent_summary") or plan["objective"])
            self._announce_intent(spec["id"], plan, shared_targets)
            self._propose_operation(spec["id"], plan)

        suggestion = self._suggest_resolution(task) if self._open_conflicts() else None
        auto_committed = []
        if not self._open_conflicts():
            for plan, spec in zip(plans, self.config.agent_specs):
                auto_committed.append(self._commit_operation(spec["id"], plan))
        return {
            "session_id": self.session_id,
            "plans": plans,
            "auto_committed": auto_committed,
            "snapshot": self.runtime.snapshot(),
            "resolution_suggestion": suggestion.to_dict() if suggestion else None,
        }

    def resolve_conflict(
        self,
        *,
        conflict_id: str,
        accepted_ids: list[str],
        rejected_ids: list[str],
        rationale: str,
    ) -> dict[str, Any]:
        payload = ResolutionPayload(
            resolution_id=f"res-{uuid.uuid4().hex[:8]}",
            conflict_id=conflict_id,
            decision=Decision.HUMAN_OVERRIDE,
            outcome=Outcome(accepted=list(accepted_ids), rejected=list(rejected_ids), merged=[]),
            rationale=rationale,
        )
        self.runtime.receive(
            self.runtime.make_envelope(
                message_type=MessageType.RESOLUTION,
                sender_id=self.config.human_id,
                sender_type=PrincipalType.HUMAN,
                payload=payload,
            )
        )
        self._commit_resolved_operations(accepted_ids)
        return {
            "session_id": self.session_id,
            "snapshot": self.runtime.snapshot(),
        }

    def snapshot(self) -> dict[str, Any]:
        suggestion = self._suggest_resolution("Existing live state") if self._open_conflicts() else None
        return {
            "session_id": self.session_id,
            "snapshot": self.runtime.snapshot(),
            "resolution_suggestion": suggestion.to_dict() if suggestion else None,
        }

    def _hello(
        self,
        principal_id: str,
        display_name: str,
        sender_type: PrincipalType,
        roles: list[str],
        capabilities: list[str],
    ) -> None:
        payload = HelloPayload(
            display_name=display_name,
            roles=roles,
            capabilities=capabilities,
            implementation={"demo": "live-playground"},
        )
        self.runtime.receive(
            self.runtime.make_envelope(
                message_type=MessageType.HELLO,
                sender_id=principal_id,
                sender_type=sender_type,
                payload=payload,
            )
        )

    def _send_heartbeat(self, principal_id: str, summary: str) -> None:
        self.runtime.receive(
            self.runtime.make_envelope(
                message_type=MessageType.HEARTBEAT,
                sender_id=principal_id,
                sender_type=PrincipalType.AGENT,
                payload=HeartbeatPayload(status="working", summary=summary),
            )
        )

    def _announce_intent(self, principal_id: str, plan: dict[str, Any], shared_targets: list[str]) -> None:
        resources = self._normalize_scope_resources(plan.get("scope_resources"), shared_targets)
        payload = IntentAnnouncePayload(
            intent_id=plan["intent_id"],
            objective=plan["objective"],
            scope=Scope(kind=ScopeKind.FILE_SET, resources=resources),
            assumptions=self._normalize_strings(plan.get("assumptions")),
            priority="normal",
            ttl_sec=600,
        )
        self.runtime.receive(
            self.runtime.make_envelope(
                message_type=MessageType.INTENT_ANNOUNCE,
                sender_id=principal_id,
                sender_type=PrincipalType.AGENT,
                payload=payload,
            )
        )

    def _propose_operation(self, principal_id: str, plan: dict[str, Any]) -> None:
        payload = OperationPayload(
            op_id=plan["op_id"],
            target=plan["target"],
            op_kind=plan["op_kind"],
            intent_id=plan["intent_id"],
            state_ref_before=plan.get("state_ref_before"),
            state_ref_after=plan.get("state_ref_after"),
            change_ref=plan.get("change_ref"),
            summary=plan.get("summary", ""),
        )
        self.runtime.receive(
            self.runtime.make_envelope(
                message_type=MessageType.OP_PROPOSE,
                sender_id=principal_id,
                sender_type=PrincipalType.AGENT,
                payload=payload,
            )
        )

    def _commit_operation(self, principal_id: str, plan: dict[str, Any]) -> str:
        payload = OperationPayload(
            op_id=plan["op_id"],
            target=plan["target"],
            op_kind=plan["op_kind"],
            intent_id=plan["intent_id"],
            state_ref_before=plan.get("state_ref_before"),
            state_ref_after=plan.get("state_ref_after"),
            change_ref=plan.get("change_ref"),
            summary=plan.get("summary", ""),
        )
        self.runtime.receive(
            self.runtime.make_envelope(
                message_type=MessageType.OP_COMMIT,
                sender_id=principal_id,
                sender_type=PrincipalType.AGENT,
                payload=payload,
            )
        )
        return payload.op_id

    def _commit_resolved_operations(self, accepted_ids: list[str]) -> None:
        operations_to_commit = []
        for identifier in accepted_ids:
            operation = self.runtime.session.operations.get(identifier)
            if operation is not None:
                operations_to_commit.append(operation)
                continue
            matched = [
                item for item in self.runtime.session.operations.values() if item.intent_id == identifier
            ]
            operations_to_commit.extend(matched)

        seen: set[str] = set()
        for operation in operations_to_commit:
            if operation.op_id in seen:
                continue
            seen.add(operation.op_id)
            if operation.target in self.runtime.session.shared_state:
                continue
            plan = {
                "op_id": operation.op_id,
                "target": operation.target,
                "op_kind": operation.op_kind,
                "intent_id": operation.intent_id,
                "state_ref_before": operation.state_ref_before,
                "state_ref_after": operation.state_ref_after or f"accepted:{operation.op_id}",
                "change_ref": operation.change_ref,
                "summary": operation.summary,
            }
            sender_type = self.runtime.session.participants[operation.principal_id].principal.principal_type
            self.runtime.receive(
                self.runtime.make_envelope(
                    message_type=MessageType.OP_COMMIT,
                    sender_id=operation.principal_id,
                    sender_type=sender_type,
                    payload=OperationPayload(**plan),
                )
            )

    def _ask_agent_for_plan(self, spec: dict[str, str], task: str, shared_targets: list[str]) -> dict[str, Any]:
        prompt = (
            "Return one JSON object only.\n"
            f"Task: {task}\n"
            f"Shared targets: {shared_targets}\n"
            f"Agent identity: {spec['name']} ({spec['id']})\n"
            f"Collaboration style: {spec['style']}\n"
            "You are participating in an MPAC coordination round. Draft your own intent and one candidate operation.\n"
            "Choose a target from the shared targets unless you intentionally want to avoid overlap.\n"
            "JSON schema:\n"
            "{\n"
            '  "objective": "short sentence",\n'
            '  "intent_summary": "short status line",\n'
            '  "scope_resources": ["path/a", "path/b"],\n'
            '  "assumptions": ["assumption 1", "assumption 2"],\n'
            '  "target": "one target path",\n'
            '  "op_kind": "edit|create|analyze|test|refactor",\n'
            '  "summary": "1-2 sentence operation summary",\n'
            '  "change_ref": "short pseudo change ref",\n'
            '  "state_ref_before": "optional short before ref",\n'
            '  "state_ref_after": "optional short after ref"\n'
            "}"
        )
        system = (
            "You are a specialized software agent in a multi-agent coordination protocol demo. "
            "Be concrete, realistic, and concise. Return valid JSON only."
        )
        raw = self.llm.complete_json(system=system, prompt=prompt, temperature=0.3)
        suffix = uuid.uuid4().hex[:6]
        return {
            "intent_id": f"intent-{spec['id'].split(':')[-1]}-{suffix}",
            "op_id": f"op-{spec['id'].split(':')[-1]}-{suffix}",
            "objective": str(raw.get("objective") or f"{spec['name']} tackles the task"),
            "intent_summary": str(raw.get("intent_summary") or raw.get("objective") or "Working"),
            "scope_resources": self._normalize_scope_resources(raw.get("scope_resources"), shared_targets),
            "assumptions": self._normalize_strings(raw.get("assumptions")),
            "target": str(raw.get("target") or shared_targets[0]),
            "op_kind": str(raw.get("op_kind") or "edit"),
            "summary": str(raw.get("summary") or "Prepared a candidate change."),
            "change_ref": str(raw.get("change_ref") or f"draft:{suffix}"),
            "state_ref_before": self._optional_string(raw.get("state_ref_before")),
            "state_ref_after": self._optional_string(raw.get("state_ref_after")) or f"candidate:{suffix}",
        }

    def _suggest_resolution(self, task: str) -> ResolutionSuggestion | None:
        conflict = self._open_conflicts()[:1]
        if not conflict:
            return None
        active = conflict[0]
        related = []
        for intent_id in active.related_intents:
            intent = self.runtime.session.intents.get(intent_id)
            if intent is None:
                continue
            related.append(
                {
                    "type": "intent",
                    "id": intent.intent_id,
                    "principal_id": intent.principal_id,
                    "objective": intent.objective,
                    "scope": intent.scope.targets(),
                    "assumptions": intent.assumptions,
                }
            )
        for op_id in active.related_ops:
            operation = self.runtime.session.operations.get(op_id)
            if operation is None:
                continue
            related.append(
                {
                    "type": "operation",
                    "id": operation.op_id,
                    "principal_id": operation.principal_id,
                    "target": operation.target,
                    "summary": operation.summary,
                }
            )
        prompt = (
            "Return one JSON object only.\n"
            f"User task: {task}\n"
            f"Conflict: {active.description}\n"
            f"Candidates: {related}\n"
            "Recommend which ids to accept and which ids to reject to move the work forward safely.\n"
            "JSON schema:\n"
            "{\n"
            '  "accepted_ids": ["id-1"],\n'
            '  "rejected_ids": ["id-2"],\n'
            '  "rationale": "short explanation"\n'
            "}"
        )
        system = (
            "You are the owner reviewing a protocol conflict. Prefer the safer plan, avoid contradictory parallel writes, "
            "and respond with valid JSON only."
        )
        raw = self.llm.complete_json(system=system, prompt=prompt, temperature=0.2)
        accepted_ids = self._normalize_strings(raw.get("accepted_ids"))
        rejected_ids = self._normalize_strings(raw.get("rejected_ids"))
        if not accepted_ids:
            if active.related_ops:
                accepted_ids = active.related_ops[:1]
                rejected_ids = active.related_ops[1:]
            elif active.related_intents:
                accepted_ids = active.related_intents[:1]
                rejected_ids = active.related_intents[1:]
        return ResolutionSuggestion(
            conflict_id=active.conflict_id,
            accepted_ids=accepted_ids,
            rejected_ids=rejected_ids,
            rationale=str(raw.get("rationale") or "Prefer a single implementation path to avoid parallel conflicting writes."),
        )

    def _open_conflicts(self) -> list[Any]:
        return [conflict for conflict in self.runtime.session.conflicts.values() if conflict.state not in {"CLOSED", "DISMISSED"}]

    def _normalize_scope_resources(self, resources: Any, fallback: list[str]) -> list[str]:
        values = self._normalize_strings(resources)
        return values or list(fallback)

    def _normalize_strings(self, values: Any) -> list[str]:
        if values is None:
            return []
        if isinstance(values, str):
            parts = [part.strip() for part in values.split(",")]
            return [part for part in parts if part]
        if isinstance(values, list):
            return [str(item).strip() for item in values if str(item).strip()]
        return []

    def _optional_string(self, value: Any) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None
