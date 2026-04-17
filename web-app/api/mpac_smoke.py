"""MPAC WebSocket smoke test: two clients, real coordinator, real protocol.

Exercises Phase D end-to-end via HTTP + WS (runs against a live FastAPI):

  1. Register Alice + Bob, Alice creates proj-alpha, invites Bob, Bob accepts.
  2. Both open WS to /ws/session/{project_id}.
  3. Both receive SESSION_INFO on HELLO.
  4. Alice sends begin_task on src/auth.py → Bob receives the INTENT_ANNOUNCE.
  5. Bob sends begin_task on the same file → both receive a CONFLICT_REPORT.
  6. Bob yields → INTENT_WITHDRAW broadcast to Alice.

Run: ``.venv/bin/python -m api.mpac_smoke``.
"""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.error
import urllib.request
import uuid

import websockets

BASE = "http://127.0.0.1:8001"
WS = "ws://127.0.0.1:8001"


def http(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise AssertionError(f"{method} {path} → {e.code}: {e.read().decode()}") from None


def check(label: str, cond: bool, detail: str = "") -> None:
    mark = "\033[32m✅\033[0m" if cond else "\033[31m❌\033[0m"
    print(f"  {mark} {label}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        raise SystemExit(1)


async def recv_until(ws, message_type: str, timeout: float = 3.0) -> dict:
    """Drain messages until one of the given type shows up (or timeout)."""
    async def _drain():
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get("message_type") == message_type:
                return msg
    return await asyncio.wait_for(_drain(), timeout=timeout)


async def run() -> None:
    print("Setting up two users + project + invite…")

    alice = http("POST", "/api/register", {
        "email": "alice-ws@test.com", "password": "pw-alice-123", "display_name": "Alice",
    })
    bob = http("POST", "/api/register", {
        "email": "bob-ws@test.com", "password": "pw-bob-123", "display_name": "Bob",
    })
    project = http("POST", "/api/projects", {"name": "proj-ws"}, token=alice["token"])
    invite = http("POST", f"/api/projects/{project['id']}/invite", {"roles": ["contributor"]},
                  token=alice["token"])
    http("POST", "/api/invites/accept", {"invite_code": invite["invite_code"]}, token=bob["token"])
    print(f"  project {project['session_id']} ready")

    a_url = f"{WS}/ws/session/{project['id']}?token={alice['token']}"
    b_url = f"{WS}/ws/session/{project['id']}?token={bob['token']}"

    print("\n1. Open WS connections")
    async with websockets.connect(a_url) as ws_a, websockets.connect(b_url) as ws_b:
        # Each side should receive a SESSION_INFO on its own HELLO.
        a_info = await recv_until(ws_a, "SESSION_INFO")
        b_info = await recv_until(ws_b, "SESSION_INFO")
        check("alice SESSION_INFO received", bool(a_info))
        check("bob SESSION_INFO received", bool(b_info))

        check(
            "session_id matches project",
            a_info["session_id"] == project["session_id"],
            a_info["session_id"],
        )

        # HELLO from each side also broadcasts a PARTICIPANT_UPDATE to others
        # (the coordinator may or may not emit one; we don't strictly require it,
        # as long as SESSION_INFO carries current participants list).

        print("\n2. Alice begins task on src/auth.py")
        alice_intent = f"intent-{uuid.uuid4().hex[:8]}"
        await ws_a.send(json.dumps({
            "action": "begin_task",
            "intent_id": alice_intent,
            "objective": "fix verify_token",
            "files": ["src/auth.py"],
        }))
        b_sees_intent = await recv_until(ws_b, "INTENT_ANNOUNCE")
        check(
            "bob receives alice's INTENT_ANNOUNCE",
            b_sees_intent["sender"]["principal_id"] == f"user:{alice['user_id']}",
            b_sees_intent["sender"]["principal_id"],
        )
        check(
            "intent references the right file",
            "src/auth.py" in b_sees_intent["payload"]["scope"]["resources"],
        )

        print("\n3. Bob also begins task on the same file → scope overlap")
        bob_intent = f"intent-{uuid.uuid4().hex[:8]}"
        await ws_b.send(json.dumps({
            "action": "begin_task",
            "intent_id": bob_intent,
            "objective": "rewrite verify_token",
            "files": ["src/auth.py"],
        }))
        a_conflict = await recv_until(ws_a, "CONFLICT_REPORT")
        b_conflict = await recv_until(ws_b, "CONFLICT_REPORT")
        check("alice receives CONFLICT_REPORT", bool(a_conflict))
        check("bob receives CONFLICT_REPORT", bool(b_conflict))
        check(
            "conflict category = scope_overlap",
            a_conflict["payload"].get("category") == "scope_overlap",
            a_conflict["payload"].get("category", "?"),
        )
        involved = {
            a_conflict["payload"].get("principal_a"),
            a_conflict["payload"].get("principal_b"),
        }
        check(
            "conflict lists both principals",
            involved == {f"user:{alice['user_id']}", f"user:{bob['user_id']}"},
            f"involved={involved}",
        )

        print("\n4. Bob yields → alice sees INTENT_WITHDRAW")
        await ws_b.send(json.dumps({
            "action": "yield_task",
            "intent_id": bob_intent,
            "reason": "polite",
        }))
        a_withdraw = await recv_until(ws_a, "INTENT_WITHDRAW")
        check(
            "alice receives INTENT_WITHDRAW from bob",
            a_withdraw["sender"]["principal_id"] == f"user:{bob['user_id']}",
        )

        print("\n5. Bad auth rejected")
    # Outside the `async with` so sockets are closed.

    bad_url = f"{WS}/ws/session/{project['id']}?token=garbage"
    try:
        async with websockets.connect(bad_url) as ws_bad:
            await ws_bad.recv()
        check("bad token rejected", False, "unexpected accept")
    except websockets.exceptions.InvalidStatus as e:
        check("bad token rejected", True, f"status={e.response.status_code}")
    except Exception as e:
        check("bad token rejected", True, f"closed: {type(e).__name__}")

    print("\n\033[32mAll MPAC WS checks passed ✓\033[0m")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except AssertionError as e:
        print(f"\n\033[31m{e}\033[0m")
        sys.exit(1)
