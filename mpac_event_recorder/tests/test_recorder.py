"""Verifies the three deletability promises:

1. ``MPAC_EVENT_LOG`` unset → ``install()`` returns False, no file created.
2. Package present + env var set → JSONL events are written.
3. (Tested in a separate harness) Package missing → import fails;
   the wrappers in main.py / relay.py swallow the ImportError.

We don't test (3) here because by definition the package isn't
importable when it's missing — the test would have to import from
outside the package. The integration test for that case is just
``rm -rf mpac_event_recorder/ && uvicorn api.main:app`` and observe
the server still starts.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "mpac-package" / "src"))
sys.path.insert(0, str(REPO_ROOT / "web-app"))

from mpac_event_recorder import recorder as rec  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_recorder():
    rec.shutdown()
    yield
    rec.shutdown()


def test_install_is_noop_when_env_var_missing(tmp_path, monkeypatch):
    monkeypatch.delenv(rec._LOG_PATH_ENV, raising=False)
    assert rec.install() is False
    assert rec.is_active() is False


def test_install_writes_started_event_when_env_set(tmp_path, monkeypatch):
    log_path = tmp_path / "session.jsonl"
    monkeypatch.setenv(rec._LOG_PATH_ENV, str(log_path))

    assert rec.install(role="web") is True
    assert rec.is_active() is True

    rec.shutdown()
    lines = [
        json.loads(line)
        for line in log_path.read_text().strip().splitlines() if line
    ]
    started = [e for e in lines if e["kind"] == "recorder_started"]
    assert len(started) == 1
    assert started[0]["role"] == "web"


def test_record_event_is_silent_when_inactive(tmp_path, monkeypatch):
    monkeypatch.delenv(rec._LOG_PATH_ENV, raising=False)
    rec.record_event("envelope", message_type="HELLO")
    # No file should exist; we passed no path.
    assert not (tmp_path / "session.jsonl").exists()


def test_logging_handler_captures_mpac_logger(tmp_path, monkeypatch):
    import logging
    log_path = tmp_path / "session.jsonl"
    monkeypatch.setenv(rec._LOG_PATH_ENV, str(log_path))
    rec.install(role="web")

    logger = logging.getLogger("mpac.test")
    logger.setLevel(logging.INFO)
    logger.info("hello %s", "world")
    rec.shutdown()

    events = [
        json.loads(line)
        for line in log_path.read_text().strip().splitlines() if line
    ]
    log_events = [e for e in events if e["kind"] == "log"]
    assert any(
        e["message"] == "hello world" and e["logger"] == "mpac.test"
        for e in log_events
    ), log_events


def test_envelope_hook_captures_coordinator_traffic(tmp_path, monkeypatch):
    log_path = tmp_path / "session.jsonl"
    monkeypatch.setenv(rec._LOG_PATH_ENV, str(log_path))
    rec.install(role="web")

    # Build a tiny session and drive an INTENT_ANNOUNCE through.
    from api.mpac_bridge import (  # noqa: E402
        ProjectSession,
        _ConnectedParticipant,
        process_envelope,
    )
    from mpac_protocol.core.coordinator import SessionCoordinator
    from mpac_protocol.core.models import Scope
    from mpac_protocol.core.participant import Participant

    session_id = "rec-test"
    session = ProjectSession(
        project_id=1,
        mpac_session_id=session_id,
        coordinator=SessionCoordinator(
            session_id=session_id, security_profile="open",
        ),
    )

    received: Dict[str, List[Dict[str, Any]]] = {}

    async def _send(pid):
        async def s(env):
            received.setdefault(pid, []).append(env)
        return s

    participant = Participant(
        principal_id="agent:user-1",
        principal_type="agent",
        display_name="Alice's Claude",
        roles=["contributor"],
        capabilities=["intent.broadcast"],
    )
    session.connections["agent:user-1"] = _ConnectedParticipant(
        principal_id="agent:user-1",
        participant=participant,
        send=asyncio.run(_send("agent:user-1")),
        display_name="Alice's Claude",
        principal_type="agent",
        roles=["contributor"],
        is_agent=True,
    )
    session.coordinator.process_message(participant.hello(session_id))

    asyncio.run(process_envelope(
        session,
        participant.announce_intent(
            session_id=session_id,
            intent_id="intent-test-1",
            objective="x",
            scope=Scope(kind="file_set", resources=["a.py"]),
        ),
        sender_principal_id="agent:user-1",
    ))

    rec.shutdown()
    events = [
        json.loads(line)
        for line in log_path.read_text().strip().splitlines() if line
    ]

    # Expect at least one envelope record for the INTENT_ANNOUNCE.
    inbound = [
        e for e in events
        if e["kind"] == "envelope" and e["direction"] == "inbound"
        and e["message_type"] == "INTENT_ANNOUNCE"
    ]
    assert inbound, [e for e in events if e["kind"] == "envelope"]
    assert inbound[0]["sender"] == "agent:user-1"

    # Expect a process_envelope_call wrapper event.
    calls = [e for e in events if e["kind"] == "process_envelope_call"]
    assert calls
    assert calls[-1]["message_type"] == "INTENT_ANNOUNCE"
