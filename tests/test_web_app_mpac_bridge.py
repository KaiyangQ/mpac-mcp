from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "mpac-package" / "src"))
sys.path.insert(0, str(REPO_ROOT / "web-app"))

from api.mpac_bridge import (  # noqa: E402
    ProjectSession,
    _ConnectedParticipant,
    _co_principal_for_owner,
    process_envelope,
)
from mpac_protocol.core.coordinator import SessionCoordinator  # noqa: E402
from mpac_protocol.core.models import Scope  # noqa: E402
from mpac_protocol.core.participant import Participant  # noqa: E402


def test_owner_principal_sibling_mapping():
    assert _co_principal_for_owner("agent:user-1") == "user:1"
    assert _co_principal_for_owner("user:1") == "agent:user-1"
    assert _co_principal_for_owner("agent:external-1") is None
    assert _co_principal_for_owner("service:coordinator-session") is None


def test_agent_conflict_report_reaches_owner_browser_sockets():
    asyncio.run(_run_agent_conflict_report_route())


async def _run_agent_conflict_report_route() -> None:
    session_id = "test-session"
    received: Dict[str, List[Dict[str, Any]]] = {}

    def make_participant(
        principal_id: str,
        principal_type: str,
        display_name: str,
    ) -> Participant:
        return Participant(
            principal_id=principal_id,
            principal_type=principal_type,
            display_name=display_name,
            roles=["contributor"],
            capabilities=["intent.broadcast"],
        )

    def make_send(principal_id: str):
        async def send(envelope: Dict[str, Any]) -> None:
            received.setdefault(principal_id, []).append(envelope)

        return send

    session = ProjectSession(
        project_id=1,
        mpac_session_id=session_id,
        coordinator=SessionCoordinator(session_id=session_id, security_profile="open"),
    )

    participants = {
        "user:1": make_participant("user:1", "human", "Alice"),
        "agent:user-1": make_participant("agent:user-1", "agent", "Alice's Claude"),
        "user:2": make_participant("user:2", "human", "Bob"),
        "agent:user-2": make_participant("agent:user-2", "agent", "Bob's Claude"),
        "user:3": make_participant("user:3", "human", "Charlie"),
    }

    for principal_id, participant in participants.items():
        received[principal_id] = []
        session.connections[principal_id] = _ConnectedParticipant(
            principal_id=principal_id,
            participant=participant,
            send=make_send(principal_id),
            display_name=participant.display_name,
            principal_type=participant.principal_type,
            roles=participant.roles,
            is_agent=principal_id.startswith("agent:"),
        )
        session.coordinator.process_message(participant.hello(session_id))

    scope = Scope(kind="file_set", resources=["src/auth.py"])
    await process_envelope(
        session,
        participants["agent:user-1"].announce_intent(
            session_id=session_id,
            intent_id="intent-alice-agent",
            objective="fix verify_token",
            scope=scope,
        ),
        sender_principal_id="agent:user-1",
    )
    for envelopes in received.values():
        envelopes.clear()

    await process_envelope(
        session,
        participants["agent:user-2"].announce_intent(
            session_id=session_id,
            intent_id="intent-bob-agent",
            objective="rewrite verify_token",
            scope=scope,
        ),
        sender_principal_id="agent:user-2",
    )

    expected_recipients = {"agent:user-1", "agent:user-2", "user:1", "user:2"}
    for principal_id in expected_recipients:
        assert any(
            envelope.get("message_type") == "CONFLICT_REPORT"
            for envelope in received[principal_id]
        ), principal_id

    assert not any(
        envelope.get("message_type") == "CONFLICT_REPORT"
        for envelope in received["user:3"]
    )
