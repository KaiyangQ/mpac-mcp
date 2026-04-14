"""Thin bridge from MCP tools to a local MPAC sidecar."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
import uuid

import websockets

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _compat import ensure_local_mpac_import
    from config import BridgeConfig, build_bridge_config
else:
    from ._compat import ensure_local_mpac_import
    from .config import BridgeConfig, build_bridge_config

ensure_local_mpac_import()

from mpac_protocol.core.models import Scope
from mpac_protocol.core.participant import Participant
from mpac_protocol.core.scope import scope_overlap


class SidecarError(RuntimeError):
    """Raised when the local sidecar cannot be started or queried."""


_BRIDGES: dict[str, "LocalParticipantBridge"] = {}


def _bridge_roles_from_env() -> list[str]:
    raw = os.environ.get("MPAC_AGENT_ROLES", "contributor")
    roles = sorted({role.strip() for role in raw.split(",") if role.strip()})
    return roles or ["contributor"]


def _bridge_capabilities_from_env() -> list[str]:
    raw = os.environ.get("MPAC_AGENT_CAPABILITIES")
    if raw:
        capabilities = sorted({cap.strip() for cap in raw.split(",") if cap.strip()})
        if capabilities:
            return capabilities
    return [
        "intent.broadcast",
        "intent.withdraw",
        "intent.claim",
        "op.commit",
        "conflict.ack",
        "conflict.escalate",
        "conflict.resolve",
    ]


def _bridge_cache_key(config: BridgeConfig) -> str:
    principal_id = os.environ.get(
        "MPAC_PRINCIPAL_ID",
        f"agent:mpac-mcp:{os.getpid()}",
    )
    role_slug = ",".join(_bridge_roles_from_env())
    return f"{config.workspace_dir}::{principal_id}::{role_slug}"


async def fetch_session_summary(config: BridgeConfig) -> dict[str, Any]:
    """Query the local sidecar for a compact session summary."""
    try:
        async with websockets.connect(config.uri) as ws:
            await ws.send(json.dumps({"type": "SESSION_SUMMARY"}))
            raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
    except Exception as exc:  # pragma: no cover - network failure surface
        raise SidecarError(f"Failed to query sidecar at {config.uri}: {exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SidecarError(f"Sidecar returned non-JSON payload: {raw!r}") from exc

    if payload.get("type") != "SESSION_SUMMARY_RESPONSE":
        raise SidecarError(f"Unexpected sidecar response: {payload}")

    summary = payload.get("session", {})
    if summary.get("session_id") != config.session_id:
        raise SidecarError(
            f"Sidecar session mismatch on {config.uri}: "
            f"expected {config.session_id}, got {summary.get('session_id')}"
        )
    return summary


async def probe_sidecar(config: BridgeConfig) -> dict[str, Any] | None:
    """Return the sidecar summary when available, otherwise None."""
    with contextlib.suppress(SidecarError):
        return await fetch_session_summary(config)
    return None


def _sidecar_script_path() -> Path:
    return Path(__file__).resolve().with_name("sidecar.py")


def start_sidecar(config: BridgeConfig) -> subprocess.Popen:
    """Launch the local sidecar as a detached Python process."""
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    return subprocess.Popen(
        [
            sys.executable,
            str(_sidecar_script_path()),
            "--workspace",
            str(config.workspace_dir),
            "--host",
            config.host,
            "--port",
            str(config.port),
            "--session-id",
            config.session_id,
        ],
        cwd=str(config.workspace_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


async def launch_ephemeral_sidecar(
    start: str | Path | None = None,
    *,
    startup_timeout_sec: float = 5.0,
) -> tuple[BridgeConfig, subprocess.Popen]:
    """Launch a new sidecar process and return both config and process handle."""
    config = build_bridge_config(start)
    summary = await probe_sidecar(config)
    if summary is not None:
        raise SidecarError(
            f"Refusing to start ephemeral sidecar because one is already running at {config.uri}"
        )

    process = start_sidecar(config)
    deadline = time.time() + startup_timeout_sec
    while time.time() < deadline:
        summary = await probe_sidecar(config)
        if summary is not None:
            return config, process
        if process.poll() is not None:
            raise SidecarError(
                f"Ephemeral sidecar exited early with code {process.returncode} "
                f"for workspace {config.workspace_dir}"
            )
        await asyncio.sleep(0.2)

    process.terminate()
    raise SidecarError(
        f"Timed out waiting for ephemeral sidecar on {config.uri} "
        f"for workspace {config.workspace_dir}"
    )


def stop_sidecar(process: subprocess.Popen | None, *, timeout_sec: float = 2.0) -> None:
    """Terminate a sidecar process that was launched ephemerally."""
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout_sec)


async def ensure_sidecar(
    start: str | Path | None = None,
    *,
    startup_timeout_sec: float = 5.0,
) -> BridgeConfig:
    """Ensure the local sidecar is running for the resolved workspace."""
    config = build_bridge_config(start)
    summary = await probe_sidecar(config)
    if summary is not None:
        return config

    process = start_sidecar(config)
    deadline = time.time() + startup_timeout_sec
    while time.time() < deadline:
        summary = await probe_sidecar(config)
        if summary is not None:
            return config
        if process.poll() is not None:
            raise SidecarError(
                f"Sidecar exited early with code {process.returncode} "
                f"for workspace {config.workspace_dir}"
            )
        await asyncio.sleep(0.2)

    raise SidecarError(
        f"Timed out waiting for sidecar on {config.uri} "
        f"for workspace {config.workspace_dir}"
    )


async def who_is_working(start: str | Path | None = None) -> dict[str, Any]:
    """Return the current shared coordination view for the workspace."""
    config = await ensure_sidecar(start)
    summary = await fetch_session_summary(config)
    return {
        "workspace_dir": str(config.workspace_dir),
        "sidecar_uri": config.uri,
        "session_id": config.session_id,
        "participant_count": summary.get("participant_count", 0),
        "active_intent_count": summary.get("active_intent_count", 0),
        "open_conflict_count": summary.get("open_conflict_count", 0),
        "participants": summary.get("participants", []),
        "active_intents": summary.get("active_intents", []),
        "open_conflicts": summary.get("open_conflicts", []),
    }


def who_is_working_sync(start: str | Path | None = None) -> dict[str, Any]:
    """Synchronous wrapper for tool hosts that prefer plain functions."""
    return asyncio.run(who_is_working(start))


class LocalParticipantBridge:
    """Persistent MPAC participant session owned by one MCP server process."""

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.name = os.environ.get("MPAC_AGENT_NAME", f"mpac-mcp-{os.getpid()}")
        self.principal_id = os.environ.get(
            "MPAC_PRINCIPAL_ID",
            f"agent:mpac-mcp:{os.getpid()}",
        )
        self.roles = _bridge_roles_from_env()
        self.participant = Participant(
            principal_id=self.principal_id,
            principal_type="agent",
            display_name=self.name,
            roles=self.roles,
            capabilities=_bridge_capabilities_from_env(),
        )
        self.ws = None
        self.protocol_inbox: asyncio.Queue = asyncio.Queue()
        self._listener_task = None
        self._connected = False
        self._owned_intents: dict[str, dict[str, Any]] = {}

    async def ensure_connected(self) -> None:
        """Ensure the local participant has an active WebSocket session."""
        if self._connected and self.ws is not None:
            return

        self.ws = await websockets.connect(self.config.uri)
        self._listener_task = asyncio.create_task(self._listen())
        await self._send(self.participant.hello(self.config.session_id))
        await self._wait_for("SESSION_INFO", timeout=2.0)
        self._connected = True

    async def _listen(self) -> None:
        try:
            async for raw in self.ws:
                data = json.loads(raw)
                if "message_type" in data:
                    await self.protocol_inbox.put(data)
        except Exception:
            self._connected = False

    async def _send(self, data: dict[str, Any]) -> None:
        await self.ws.send(json.dumps(data, ensure_ascii=False))

    async def _wait_for(self, message_type: str, timeout: float = 2.0) -> dict[str, Any] | None:
        deadline = time.time() + timeout
        stash = []
        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(
                    self.protocol_inbox.get(),
                    timeout=max(0.1, deadline - time.time()),
                )
            except asyncio.TimeoutError:
                break
            if msg.get("message_type") == message_type:
                for item in stash:
                    await self.protocol_inbox.put(item)
                return msg
            stash.append(msg)

        for item in stash:
            await self.protocol_inbox.put(item)
        return None

    async def drain_protocol_messages(self, duration: float = 0.5) -> list[dict[str, Any]]:
        """Collect protocol messages for a short period."""
        deadline = time.time() + duration
        items: list[dict[str, Any]] = []
        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(
                    self.protocol_inbox.get(),
                    timeout=max(0.05, deadline - time.time()),
                )
            except asyncio.TimeoutError:
                break
            items.append(msg)
        return items

    async def begin_task(self, objective: str, files: list[str]) -> dict[str, Any]:
        """Announce a file-scoped intent and return the resulting state view."""
        await self.ensure_connected()

        normalized_files = sorted({str(file) for file in files if str(file).strip()})
        intent_id = f"intent-{self.name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        await self._send(
            self.participant.announce_intent(
                self.config.session_id,
                intent_id,
                objective,
                Scope(kind="file_set", resources=normalized_files),
            )
        )
        await asyncio.sleep(0.3)
        messages = await self.drain_protocol_messages(0.6)
        summary = await fetch_session_summary(self.config)

        conflicts = [
            msg.get("payload", {})
            for msg in messages
            if msg.get("message_type") == "CONFLICT_REPORT"
            and intent_id in {
                msg.get("payload", {}).get("intent_a"),
                msg.get("payload", {}).get("intent_b"),
            }
        ]
        errors = [
            msg.get("payload", {})
            for msg in messages
            if msg.get("message_type") == "PROTOCOL_ERROR"
        ]

        own_intent = next(
            (intent for intent in summary.get("active_intents", []) if intent.get("intent_id") == intent_id),
            None,
        )
        if not errors:
            self._owned_intents[intent_id] = {
                "objective": objective,
                "files": normalized_files,
            }

        return {
            "status": "error" if errors else "ok",
            "intent_id": intent_id,
            "principal_id": self.principal_id,
            "objective": objective,
            "files": normalized_files,
            "has_conflict": bool(conflicts),
            "conflicts": conflicts,
            "errors": errors,
            "intent": own_intent,
        }

    async def yield_task(self, intent_id: str, reason: str = "yielded") -> dict[str, Any]:
        """Withdraw an owned intent."""
        await self.ensure_connected()
        if intent_id not in self._owned_intents:
            return {
                "status": "error",
                "intent_id": intent_id,
                "message": "Intent is not owned by this MCP bridge process",
            }

        await self._send(
            self.participant.withdraw_intent(
                self.config.session_id,
                intent_id,
                reason,
            )
        )
        await asyncio.sleep(0.2)
        self._owned_intents.pop(intent_id, None)
        summary = await fetch_session_summary(self.config)
        return {
            "status": "ok",
            "intent_id": intent_id,
            "message": f"Intent withdrawn: {reason}",
            "active_intent_count": summary.get("active_intent_count", 0),
        }

    async def submit_change(
        self,
        intent_id: str,
        target: str,
        content: str,
        state_ref_before: str,
    ) -> dict[str, Any]:
        """Attempt a single OP_COMMIT and return a product-style result."""
        await self.ensure_connected()
        if intent_id not in self._owned_intents:
            return {
                "status": "error",
                "intent_id": intent_id,
                "target": target,
                "message": "Intent is not owned by this MCP bridge process",
                "conflicting_files": [target],
            }

        op_id = f"op-{self.name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        state_ref_after = _sha_ref(content)
        msg = self.participant.commit_op(
            self.config.session_id,
            op_id,
            intent_id,
            target,
            "replace",
            state_ref_before=state_ref_before,
            state_ref_after=state_ref_after,
        )
        msg["payload"]["file_changes"] = {
            target: {
                "content": content,
                "state_ref_before": state_ref_before,
            }
        }
        await self._send(msg)
        await asyncio.sleep(0.4)
        messages = await self.drain_protocol_messages(0.8)

        protocol_errors = [
            payload
            for payload in (
                msg.get("payload", {})
                for msg in messages
                if msg.get("message_type") == "PROTOCOL_ERROR"
            )
        ]
        stale_error = next(
            (payload for payload in protocol_errors if payload.get("error_code") == "STALE_STATE_REF"),
            None,
        )
        frozen_error = next(
            (payload for payload in protocol_errors if payload.get("error_code") == "SCOPE_FROZEN"),
            None,
        )

        file_state = await fetch_file_state(self.config, target)
        current_state_ref = file_state.get("state_ref") if file_state else None

        if stale_error:
            return {
                "status": "stale",
                "intent_id": intent_id,
                "target": target,
                "current_state_ref": current_state_ref,
                "conflicting_files": [target],
                "message": stale_error.get("description", "State ref is stale; refresh and retry"),
            }

        if frozen_error:
            return {
                "status": "conflict",
                "intent_id": intent_id,
                "target": target,
                "current_state_ref": current_state_ref,
                "conflicting_files": [target],
                "message": frozen_error.get("description", "Scope is frozen"),
            }

        if protocol_errors:
            return {
                "status": "error",
                "intent_id": intent_id,
                "target": target,
                "current_state_ref": current_state_ref,
                "conflicting_files": [target],
                "message": protocol_errors[0].get("description", "Commit rejected"),
            }

        return {
            "status": "success",
            "intent_id": intent_id,
            "target": target,
            "state_ref_after": state_ref_after,
            "current_state_ref": current_state_ref or state_ref_after,
            "conflicting_files": [],
            "message": "Commit accepted",
        }

    async def resolve_conflict(
        self,
        conflict_id: str,
        decision: str,
        rationale: str | None = None,
        outcome: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Attempt to resolve a conflict with the current bridge identity."""
        await self.ensure_connected()
        await self._send(
            self.participant.resolve_conflict(
                self.config.session_id,
                conflict_id,
                decision,
                rationale=rationale,
                outcome=outcome,
            )
        )
        await asyncio.sleep(0.3)
        messages = await self.drain_protocol_messages(0.7)
        protocol_errors = [
            payload
            for payload in (
                msg.get("payload", {})
                for msg in messages
                if msg.get("message_type") == "PROTOCOL_ERROR"
            )
        ]
        updated = await fetch_session_summary(self.config)
        remaining = next(
            (
                conflict
                for conflict in updated.get("open_conflicts", [])
                if conflict.get("conflict_id") == conflict_id
            ),
            None,
        )
        if protocol_errors:
            return {
                "status": "error",
                "conflict_id": conflict_id,
                "decision": decision,
                "message": protocol_errors[0].get("description", "Resolution rejected"),
                "open_conflicts": updated.get("open_conflicts", []),
            }

        return {
            "status": "ok",
            "conflict_id": conflict_id,
            "decision": decision,
            "remaining_conflict": remaining,
            "open_conflicts": updated.get("open_conflicts", []),
            "message": "Conflict resolution submitted",
        }


async def get_local_bridge(start: str | Path | None = None) -> LocalParticipantBridge:
    """Return the per-workspace participant bridge, creating it if needed."""
    config = await ensure_sidecar(start)
    key = _bridge_cache_key(config)
    bridge = _BRIDGES.get(key)
    if bridge is None:
        bridge = LocalParticipantBridge(config)
        _BRIDGES[key] = bridge
    await bridge.ensure_connected()
    return bridge


def _files_scope(files: list[str]) -> Scope:
    return Scope(kind="file_set", resources=sorted({str(f) for f in files if str(f).strip()}))


def _sha_ref(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


async def fetch_file_state(config: BridgeConfig, path: str) -> dict[str, Any] | None:
    """Read one file from the sidecar workspace using a temporary connection."""
    try:
        async with websockets.connect(config.uri) as ws:
            await ws.send(json.dumps({"type": "FILE_READ", "path": path}))
            raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
    except Exception as exc:  # pragma: no cover - network failure surface
        raise SidecarError(f"Failed to read file '{path}' from sidecar: {exc}") from exc

    payload = json.loads(raw)
    if payload.get("type") == "FILE_ERROR":
        return None
    if payload.get("type") != "FILE_CONTENT":
        raise SidecarError(f"Unexpected FILE_READ response for '{path}': {payload}")
    return payload


async def get_file_state(
    path: str,
    start: str | Path | None = None,
    *,
    include_content: bool = True,
) -> dict[str, Any]:
    """Return the current file state from the shared sidecar workspace."""
    config = await ensure_sidecar(start)
    payload = await fetch_file_state(config, path)
    if payload is None:
        return {
            "status": "missing",
            "path": path,
            "workspace_dir": str(config.workspace_dir),
            "session_id": config.session_id,
            "message": "File not found in shared workspace",
        }

    result = {
        "status": "ok",
        "path": path,
        "state_ref": payload["state_ref"],
        "workspace_dir": str(config.workspace_dir),
        "session_id": config.session_id,
        "size": len(payload.get("content", "")),
    }
    if include_content:
        result["content"] = payload.get("content", "")
    return result


async def check_overlap(
    files: list[str],
    start: str | Path | None = None,
) -> dict[str, Any]:
    """Check whether a proposed file set overlaps active intents."""
    bridge = await get_local_bridge(start)
    summary = await fetch_session_summary(bridge.config)
    proposed = _files_scope(files)

    overlaps = []
    for intent in summary.get("active_intents", []):
        if intent.get("principal_id") == bridge.principal_id:
            continue
        scope_data = intent.get("scope") or {}
        try:
            existing_scope = Scope.from_dict(scope_data)
        except Exception:
            continue
        if scope_overlap(proposed, existing_scope):
            overlaps.append(
                {
                    "intent_id": intent.get("intent_id"),
                    "principal_id": intent.get("principal_id"),
                    "objective": intent.get("objective"),
                    "scope": scope_data,
                }
            )

    return {
        "workspace_dir": str(bridge.config.workspace_dir),
        "session_id": bridge.config.session_id,
        "proposed_files": proposed.resources or [],
        "has_overlap": bool(overlaps),
        "overlaps": overlaps,
    }


def _choose_arbiter(summary: dict[str, Any]) -> str | None:
    arbiters = [
        participant["principal_id"]
        for participant in summary.get("participants", [])
        if "arbiter" in set(participant.get("roles", []))
        and participant.get("is_available", False)
    ]
    if len(arbiters) == 1:
        return arbiters[0]
    return None


async def begin_task(
    objective: str,
    files: list[str],
    start: str | Path | None = None,
) -> dict[str, Any]:
    """Announce a task through the local participant bridge."""
    bridge = await get_local_bridge(start)
    result = await bridge.begin_task(objective, files)
    result.update(
        {
            "workspace_dir": str(bridge.config.workspace_dir),
            "session_id": bridge.config.session_id,
        }
    )
    return result


async def ack_conflict(
    conflict_id: str,
    ack_type: str = "seen",
    start: str | Path | None = None,
) -> dict[str, Any]:
    """Acknowledge or dispute a conflict."""
    bridge = await get_local_bridge(start)
    await bridge.ensure_connected()
    await bridge._send(
        bridge.participant.ack_conflict(
            bridge.config.session_id,
            conflict_id,
            ack_type,
        )
    )
    await asyncio.sleep(0.2)
    summary = await fetch_session_summary(bridge.config)
    return {
        "status": "ok",
        "conflict_id": conflict_id,
        "ack_type": ack_type,
        "workspace_dir": str(bridge.config.workspace_dir),
        "session_id": bridge.config.session_id,
        "open_conflicts": summary.get("open_conflicts", []),
    }


async def escalate_conflict(
    conflict_id: str,
    reason: str,
    start: str | Path | None = None,
    *,
    escalate_to: str | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    """Escalate a conflict to an explicit or inferred arbiter."""
    bridge = await get_local_bridge(start)
    await bridge.ensure_connected()
    summary = await fetch_session_summary(bridge.config)

    resolved_target = escalate_to or _choose_arbiter(summary)
    if resolved_target is None:
        return {
            "status": "error",
            "conflict_id": conflict_id,
            "workspace_dir": str(bridge.config.workspace_dir),
            "session_id": bridge.config.session_id,
            "message": "No unique available arbiter found; pass escalate_to explicitly",
        }

    await bridge._send(
        bridge.participant.escalate_conflict(
            bridge.config.session_id,
            conflict_id,
            resolved_target,
            reason,
            context=context,
        )
    )
    await asyncio.sleep(0.3)
    updated = await fetch_session_summary(bridge.config)
    return {
        "status": "ok",
        "conflict_id": conflict_id,
        "escalate_to": resolved_target,
        "workspace_dir": str(bridge.config.workspace_dir),
        "session_id": bridge.config.session_id,
        "open_conflicts": updated.get("open_conflicts", []),
    }


async def yield_task(
    intent_id: str,
    reason: str = "yielded",
    start: str | Path | None = None,
) -> dict[str, Any]:
    """Withdraw an existing owned intent."""
    bridge = await get_local_bridge(start)
    result = await bridge.yield_task(intent_id, reason)
    result.update(
        {
            "workspace_dir": str(bridge.config.workspace_dir),
            "session_id": bridge.config.session_id,
        }
    )
    return result


async def take_over_task(
    original_intent_id: str,
    start: str | Path | None = None,
    *,
    new_objective: str | None = None,
    files: list[str] | None = None,
    original_principal_id: str | None = None,
    justification: str | None = None,
) -> dict[str, Any]:
    """Claim a suspended intent and create a replacement owned intent."""
    bridge = await get_local_bridge(start)
    await bridge.ensure_connected()
    summary = await fetch_session_summary(bridge.config)

    original = next(
        (
            intent for intent in summary.get("active_intents", [])
            if intent.get("intent_id") == original_intent_id
        ),
        None,
    )
    if original is None:
        return {
            "status": "error",
            "original_intent_id": original_intent_id,
            "workspace_dir": str(bridge.config.workspace_dir),
            "session_id": bridge.config.session_id,
            "message": "Original intent not found in sidecar summary",
        }

    scope_data = original.get("scope") or {}
    scope = Scope.from_dict(scope_data)
    claim_files = files or scope.resources or []
    claim_objective = new_objective or original.get("objective") or "Continue claimed work"
    claim_id = f"claim-{bridge.name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
    new_intent_id = f"intent-{bridge.name.lower().replace(' ', '-')}-claim-{uuid.uuid4().hex[:8]}"
    owner_id = original_principal_id or original.get("principal_id")

    await bridge._send(
        bridge.participant.claim_intent(
            bridge.config.session_id,
            claim_id,
            original_intent_id,
            owner_id,
            new_intent_id,
            claim_objective,
            Scope(kind=scope.kind, resources=claim_files or None, entities=scope.entities, task_ids=scope.task_ids),
            justification=justification,
        )
    )
    response = await bridge._wait_for("INTENT_CLAIM_STATUS", timeout=3.0)
    if response is None:
        return {
            "status": "timeout",
            "original_intent_id": original_intent_id,
            "new_intent_id": new_intent_id,
            "workspace_dir": str(bridge.config.workspace_dir),
            "session_id": bridge.config.session_id,
            "message": "Timed out waiting for INTENT_CLAIM_STATUS",
        }

    payload = response.get("payload", {})
    decision = payload.get("decision", "unknown")
    if decision == "approved":
        bridge._owned_intents[new_intent_id] = {
            "objective": claim_objective,
            "files": claim_files,
        }

    return {
        "status": "ok" if decision == "approved" else decision,
        "decision": decision,
        "claim_id": claim_id,
        "original_intent_id": original_intent_id,
        "new_intent_id": new_intent_id,
        "workspace_dir": str(bridge.config.workspace_dir),
        "session_id": bridge.config.session_id,
        "message": payload.get("reason", f"Claim decision: {decision}"),
    }


async def resolve_conflict(
    conflict_id: str,
    decision: str,
    start: str | Path | None = None,
    *,
    rationale: str | None = None,
    outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a conflict through the local participant bridge."""
    bridge = await get_local_bridge(start)
    result = await bridge.resolve_conflict(
        conflict_id,
        decision,
        rationale=rationale,
        outcome=outcome,
    )
    result.update(
        {
            "workspace_dir": str(bridge.config.workspace_dir),
            "session_id": bridge.config.session_id,
        }
    )
    return result


async def submit_change(
    intent_id: str,
    target: str,
    content: str,
    state_ref_before: str,
    start: str | Path | None = None,
) -> dict[str, Any]:
    """Attempt one commit and return success/stale/conflict/error."""
    bridge = await get_local_bridge(start)
    result = await bridge.submit_change(intent_id, target, content, state_ref_before)
    result.update(
        {
            "workspace_dir": str(bridge.config.workspace_dir),
            "session_id": bridge.config.session_id,
        }
    )
    return result
