"""Focused tests for the MPAC reference runtime."""

from __future__ import annotations

import unittest

from mpac import MPACRuntime
from mpac.agents.mock_agent import MockAgent
from mpac.models import (
    HelloPayload,
    IntentAnnouncePayload,
    MessageType,
    OperationPayload,
    Principal,
    PrincipalType,
    Role,
    Scope,
    ScopeKind,
)


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = MPACRuntime(session_id="sess-test")
        owner = Principal(
            principal_id="human:owner",
            principal_type=PrincipalType.HUMAN,
            display_name="Owner",
            roles=[Role.OWNER, Role.ARBITER],
            capabilities=["governance.override"],
        )
        self.runtime.register_agent(MockAgent(principal=owner, auto_resolve_escalations=True))
        self._hello("human:owner", PrincipalType.HUMAN, "Owner", ["owner", "arbiter"], ["governance.override"])
        self._hello("agent:a", PrincipalType.AGENT, "Agent A", ["contributor"], ["intent.broadcast", "op.propose", "op.commit"])
        self._hello("agent:b", PrincipalType.AGENT, "Agent B", ["contributor"], ["intent.broadcast", "op.propose", "op.commit"])

    def test_join_and_presence(self) -> None:
        snapshot = self.runtime.snapshot()
        self.assertIn("agent:a", snapshot["participants"])
        self.assertTrue(snapshot["participants"]["agent:a"]["joined"])

    def test_intent_overlap_creates_conflict_and_resolution(self) -> None:
        self._announce("agent:a", "intent-a", ["train.py"])
        self._announce("agent:b", "intent-b", ["train.py"])

        conflicts = self.runtime.snapshot()["conflicts"]
        self.assertEqual(len(conflicts), 1)
        conflict = next(iter(conflicts.values()))
        self.assertEqual(conflict["state"], "CLOSED")
        self.assertEqual(len(self.runtime.snapshot()["resolutions"]), 1)

    def test_commit_updates_shared_state(self) -> None:
        self._announce("agent:a", "intent-a", ["train.py"])
        self.runtime.receive(
            self.runtime.make_envelope(
                message_type=MessageType.OP_COMMIT,
                sender_id="agent:a",
                sender_type=PrincipalType.AGENT,
                payload=OperationPayload(
                    op_id="op-a",
                    intent_id="intent-a",
                    target="train.py",
                    op_kind="replace",
                    state_ref_before="sha256:old",
                    state_ref_after="sha256:new",
                    change_ref="sha256:diff",
                    summary="Update train config",
                ),
            )
        )
        self.assertEqual(self.runtime.snapshot()["shared_state"]["train.py"], "sha256:new")

    def _hello(self, principal_id: str, principal_type: PrincipalType, display_name: str, roles: list[str], capabilities: list[str]) -> None:
        self.runtime.receive(
            self.runtime.make_envelope(
                message_type=MessageType.HELLO,
                sender_id=principal_id,
                sender_type=principal_type,
                payload=HelloPayload(
                    display_name=display_name,
                    roles=roles,
                    capabilities=capabilities,
                    implementation={"name": "tests", "version": "0.1.0"},
                ),
            )
        )

    def _announce(self, principal_id: str, intent_id: str, resources: list[str]) -> None:
        self.runtime.receive(
            self.runtime.make_envelope(
                message_type=MessageType.INTENT_ANNOUNCE,
                sender_id=principal_id,
                sender_type=PrincipalType.AGENT,
                payload=IntentAnnouncePayload(
                    intent_id=intent_id,
                    objective="Edit file",
                    scope=Scope(kind=ScopeKind.FILE_SET, resources=resources),
                    assumptions=[],
                    ttl_sec=20,
                ),
            )
        )


if __name__ == "__main__":
    unittest.main()
