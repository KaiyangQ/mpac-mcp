import asyncio

import mpac_mcp.coordinator_bridge as bridge


class DummyBridge:
    def __init__(self):
        self.principal_id = "agent:test"
        self.config = type(
            "Config",
            (),
            {
                "workspace_dir": "/tmp/repo",
                "session_id": "session-123",
            },
        )()

    async def begin_task(self, objective, files):
        return {
            "status": "ok",
            "intent_id": "intent-123",
            "principal_id": self.principal_id,
            "objective": objective,
            "files": files,
            "has_conflict": False,
            "conflicts": [],
            "errors": [],
            "intent": {"intent_id": "intent-123"},
        }

    async def yield_task(self, intent_id, reason="yielded"):
        return {
            "status": "ok",
            "intent_id": intent_id,
            "message": f"Intent withdrawn: {reason}",
            "active_intent_count": 0,
        }

    async def submit_change(self, intent_id, target, content, state_ref_before):
        return {
            "status": "success",
            "intent_id": intent_id,
            "target": target,
            "state_ref_after": "sha256:new",
            "current_state_ref": "sha256:new",
            "conflicting_files": [],
            "message": "Commit accepted",
        }

    async def resolve_conflict(self, conflict_id, decision, rationale=None, outcome=None):
        return {
            "status": "ok",
            "conflict_id": conflict_id,
            "decision": decision,
            "remaining_conflict": None,
            "open_conflicts": [],
            "message": rationale or "Conflict resolution submitted",
        }


def test_check_overlap_filters_own_intents(monkeypatch):
    dummy_bridge = DummyBridge()

    async def fake_get_local_bridge(start=None):
        return dummy_bridge

    async def fake_fetch_session_summary(config):
        return {
            "active_intents": [
                {
                    "intent_id": "intent-self",
                    "principal_id": "agent:test",
                    "objective": "my own task",
                    "scope": {"kind": "file_set", "resources": ["auth.py"]},
                },
                {
                    "intent_id": "intent-other",
                    "principal_id": "agent:other",
                    "objective": "other task",
                    "scope": {"kind": "file_set", "resources": ["auth.py"]},
                },
            ]
        }

    monkeypatch.setattr(bridge, "get_local_bridge", fake_get_local_bridge)
    monkeypatch.setattr(bridge, "fetch_session_summary", fake_fetch_session_summary)

    result = asyncio.run(bridge.check_overlap(["auth.py"]))
    assert result["has_overlap"] is True
    assert len(result["overlaps"]) == 1
    assert result["overlaps"][0]["principal_id"] == "agent:other"


def test_begin_task_adds_workspace_context(monkeypatch):
    dummy_bridge = DummyBridge()

    async def fake_get_local_bridge(start=None):
        return dummy_bridge

    monkeypatch.setattr(bridge, "get_local_bridge", fake_get_local_bridge)

    result = asyncio.run(bridge.begin_task("Fix auth", ["auth.py"]))
    assert result["status"] == "ok"
    assert result["workspace_dir"] == "/tmp/repo"
    assert result["session_id"] == "session-123"


def test_yield_task_adds_workspace_context(monkeypatch):
    dummy_bridge = DummyBridge()

    async def fake_get_local_bridge(start=None):
        return dummy_bridge

    monkeypatch.setattr(bridge, "get_local_bridge", fake_get_local_bridge)

    result = asyncio.run(bridge.yield_task("intent-123", "manual_yield"))
    assert result["status"] == "ok"
    assert result["workspace_dir"] == "/tmp/repo"
    assert result["session_id"] == "session-123"


def test_submit_change_adds_workspace_context(monkeypatch):
    dummy_bridge = DummyBridge()

    async def fake_get_local_bridge(start=None):
        return dummy_bridge

    monkeypatch.setattr(bridge, "get_local_bridge", fake_get_local_bridge)

    result = asyncio.run(
        bridge.submit_change("intent-123", "auth.py", "print('ok')", "sha256:old")
    )
    assert result["status"] == "success"
    assert result["workspace_dir"] == "/tmp/repo"
    assert result["session_id"] == "session-123"


def test_resolve_conflict_adds_workspace_context(monkeypatch):
    dummy_bridge = DummyBridge()

    async def fake_get_local_bridge(start=None):
        return dummy_bridge

    monkeypatch.setattr(bridge, "get_local_bridge", fake_get_local_bridge)

    result = asyncio.run(
        bridge.resolve_conflict(
            "conflict-123",
            "approved",
            rationale="arbiter approved",
        )
    )
    assert result["status"] == "ok"
    assert result["conflict_id"] == "conflict-123"
    assert result["workspace_dir"] == "/tmp/repo"
    assert result["session_id"] == "session-123"


def test_get_file_state_returns_content(monkeypatch):
    async def fake_ensure_sidecar(start=None, startup_timeout_sec=5.0):
        return type(
            "Config",
            (),
            {
                "workspace_dir": "/tmp/repo",
                "session_id": "session-123",
                "uri": "ws://127.0.0.1:39999",
            },
        )()

    async def fake_fetch_file_state(config, path):
        return {
            "type": "FILE_CONTENT",
            "path": path,
            "content": "hello",
            "state_ref": "sha256:abc",
        }

    monkeypatch.setattr(bridge, "ensure_sidecar", fake_ensure_sidecar)
    monkeypatch.setattr(bridge, "fetch_file_state", fake_fetch_file_state)

    result = asyncio.run(bridge.get_file_state("README.md"))
    assert result["status"] == "ok"
    assert result["path"] == "README.md"
    assert result["state_ref"] == "sha256:abc"
    assert result["content"] == "hello"


def test_choose_arbiter_returns_unique_available_arbiter():
    summary = {
        "participants": [
            {"principal_id": "agent:a", "roles": ["contributor"], "is_available": True},
            {"principal_id": "human:arbiter", "roles": ["arbiter"], "is_available": True},
        ]
    }
    assert bridge._choose_arbiter(summary) == "human:arbiter"


def test_choose_arbiter_returns_none_when_ambiguous():
    summary = {
        "participants": [
            {"principal_id": "arbiter:one", "roles": ["arbiter"], "is_available": True},
            {"principal_id": "arbiter:two", "roles": ["arbiter"], "is_available": True},
        ]
    }
    assert bridge._choose_arbiter(summary) is None


def test_bridge_cache_key_changes_with_identity(monkeypatch):
    config = type("Config", (), {"workspace_dir": "/tmp/repo"})()
    monkeypatch.setenv("MPAC_PRINCIPAL_ID", "agent:first")
    monkeypatch.setenv("MPAC_AGENT_ROLES", "contributor")
    key_one = bridge._bridge_cache_key(config)

    monkeypatch.setenv("MPAC_PRINCIPAL_ID", "agent:arbiter")
    monkeypatch.setenv("MPAC_AGENT_ROLES", "arbiter")
    key_two = bridge._bridge_cache_key(config)

    assert key_one != key_two
