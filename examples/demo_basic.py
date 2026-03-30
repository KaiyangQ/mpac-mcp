"""Runnable MPAC demo with two contributors and one owner."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


def main() -> None:
    runtime = MPACRuntime(session_id="sess-demo")

    owner = Principal(
        principal_id="human:maya",
        principal_type=PrincipalType.HUMAN,
        display_name="Maya",
        roles=[Role.OWNER, Role.ARBITER],
        capabilities=["governance.override"],
    )
    runtime.register_agent(MockAgent(principal=owner, auto_resolve_escalations=True))

    runtime.receive(
        runtime.make_envelope(
            message_type=MessageType.HELLO,
            sender_id="human:maya",
            sender_type=PrincipalType.HUMAN,
            payload=HelloPayload(
                display_name="Maya",
                roles=["owner", "arbiter"],
                capabilities=["governance.override"],
                implementation={"name": "mpac-demo", "version": "0.1.0"},
            ),
        )
    )

    for principal_id, display_name in [("agent:backend-1", "Backend Agent"), ("agent:db-1", "DB Agent")]:
        runtime.receive(
            runtime.make_envelope(
                message_type=MessageType.HELLO,
                sender_id=principal_id,
                sender_type=PrincipalType.AGENT,
                payload=HelloPayload(
                    display_name=display_name,
                    roles=["contributor"],
                    capabilities=["intent.broadcast", "op.propose", "op.commit"],
                    implementation={"name": "mpac-demo", "version": "0.1.0"},
                ),
            )
        )

    runtime.receive(
        runtime.make_envelope(
            message_type=MessageType.INTENT_ANNOUNCE,
            sender_id="agent:backend-1",
            sender_type=PrincipalType.AGENT,
            payload=IntentAnnouncePayload(
                intent_id="intent-api",
                objective="Implement registration endpoint",
                scope=Scope(kind=ScopeKind.FILE_SET, resources=["src/routes/auth.ts", "src/services/user.ts"]),
                assumptions=["bcrypt is the agreed hashing algorithm"],
                ttl_sec=30,
            ),
        )
    )
    runtime.receive(
        runtime.make_envelope(
            message_type=MessageType.INTENT_ANNOUNCE,
            sender_id="agent:db-1",
            sender_type=PrincipalType.AGENT,
            payload=IntentAnnouncePayload(
                intent_id="intent-db",
                objective="Modify user persistence",
                scope=Scope(kind=ScopeKind.FILE_SET, resources=["src/services/user.ts", "db/schema.sql"]),
                assumptions=["bcrypt is the agreed hashing algorithm"],
                ttl_sec=30,
            ),
        )
    )
    runtime.receive(
        runtime.make_envelope(
            message_type=MessageType.OP_COMMIT,
            sender_id="agent:backend-1",
            sender_type=PrincipalType.AGENT,
            payload=OperationPayload(
                op_id="op-auth",
                intent_id="intent-api",
                target="src/services/user.ts",
                op_kind="replace",
                state_ref_before="sha256:before-1",
                state_ref_after="sha256:after-1",
                change_ref="sha256:diff-1",
                summary="Add registration service flow",
            ),
        )
    )

    print(json.dumps(runtime.snapshot(), indent=2))


if __name__ == "__main__":
    main()
