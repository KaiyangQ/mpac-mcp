"""End-to-end smoke test for v0.2.1 cross-file dependency-breakage detection.

Extends ``mpac_smoke.py`` with the scenario the user specifically asked for:

  1. Alice + Bob join a project.
  2. Project is seeded with ``utils.py`` + ``main.py`` where ``main.py``
     imports ``foo`` from ``utils.py``.
  3. Alice begins a task on ``utils.py``.
     * The web-app's announce path runs ``compute_scope_impact`` against
       the DB-backed project files and attaches ``extensions.impact =
       ["main.py"]`` to her scope.
  4. Bob begins a task on ``main.py`` — disjoint resources, so classical
     path-level overlap WOULD miss it.
  5. Both WS clients must receive a ``CONFLICT_REPORT`` with category
     ``dependency_breakage``.

Run against a live FastAPI (``127.0.0.1:8001``)::

    PYTHONPATH="../mpac-package/src:api" \\
      ../.venv/bin/python -m api.mpac_dep_smoke
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
    async def _drain():
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get("message_type") == message_type:
                return msg
    return await asyncio.wait_for(_drain(), timeout=timeout)


async def run() -> None:
    print("Setting up two users + project + invite…")

    # Each smoke run uses fresh emails so it can be re-run against the same DB.
    # Invite codes come from MPAC_WEB_INVITE_CODES on the server side; the
    # caller is expected to seed at least two codes (see the Bash command in
    # the module docstring).
    nonce = uuid.uuid4().hex[:6]
    alice = http("POST", "/api/register", {
        "email": f"alice-dep-{nonce}@test.com",
        "password": "pw-alice-123",
        "display_name": "Alice",
        "invite_code": "DEPSMOKE-A",
    })
    bob = http("POST", "/api/register", {
        "email": f"bob-dep-{nonce}@test.com",
        "password": "pw-bob-123",
        "display_name": "Bob",
        "invite_code": "DEPSMOKE-B",
    })
    project = http(
        "POST", "/api/projects", {"name": f"proj-dep-{nonce}"},
        token=alice["token"],
    )
    invite = http(
        "POST", f"/api/projects/{project['id']}/invite",
        {"roles": ["contributor"]},
        token=alice["token"],
    )
    http(
        "POST", "/api/invites/accept",
        {"invite_code": invite["invite_code"]},
        token=bob["token"],
    )
    print(f"  project {project['session_id']} ready (id={project['id']})")

    print("\n1. Seed project with utils.py + main.py (main imports utils)")
    pid = project["id"]
    http(
        "PUT", f"/api/projects/{pid}/files/content",
        {"path": "utils.py", "content": "def foo():\n    return 1\n"},
        token=alice["token"],
    )
    http(
        "PUT", f"/api/projects/{pid}/files/content",
        {"path": "main.py", "content": "from utils import foo\n\nprint(foo())\n"},
        token=alice["token"],
    )
    # A decoy file that does NOT touch utils — it should not appear anywhere.
    http(
        "PUT", f"/api/projects/{pid}/files/content",
        {"path": "README.md", "content": "# not python\n"},
        token=alice["token"],
    )
    files_list = http(
        "GET", f"/api/projects/{pid}/files", token=alice["token"],
    )
    paths = {f["path"] for f in files_list.get("files", [])}
    check("utils.py seeded", "utils.py" in paths)
    check("main.py seeded", "main.py" in paths)

    a_url = f"{WS}/ws/session/{pid}?token={alice['token']}"
    b_url = f"{WS}/ws/session/{pid}?token={bob['token']}"

    print("\n2. Open WS for both users")
    async with websockets.connect(a_url) as ws_a, websockets.connect(b_url) as ws_b:
        await recv_until(ws_a, "SESSION_INFO")
        await recv_until(ws_b, "SESSION_INFO")
        check("both sides received SESSION_INFO", True)

        print("\n3. Alice begins task on utils.py")
        alice_intent = f"intent-{uuid.uuid4().hex[:8]}"
        await ws_a.send(json.dumps({
            "action": "begin_task",
            "intent_id": alice_intent,
            "objective": "refactor helper",
            "files": ["utils.py"],
        }))
        b_sees_intent = await recv_until(ws_b, "INTENT_ANNOUNCE")
        scope = b_sees_intent["payload"]["scope"]
        check(
            "intent references utils.py",
            "utils.py" in scope.get("resources", []),
            scope.get("resources"),
        )
        # This is the heart of the new feature — the announce path must have
        # enriched Alice's scope with the reverse-dep set from the DB scan.
        impact = (scope.get("extensions") or {}).get("impact") or []
        check(
            "scope carries computed impact=[main.py]",
            impact == ["main.py"],
            f"impact={impact}",
        )

        print("\n4. Bob begins task on main.py (disjoint resources; "
              "only cross-file dep links them)")
        bob_intent = f"intent-{uuid.uuid4().hex[:8]}"
        await ws_b.send(json.dumps({
            "action": "begin_task",
            "intent_id": bob_intent,
            "objective": "fix entrypoint",
            "files": ["main.py"],
        }))

        # Classic v0.2.0 behaviour would be: silence (no CONFLICT_REPORT),
        # because resources {utils.py} ∩ {main.py} = ∅. v0.2.1 must flag it.
        a_conflict = await recv_until(ws_a, "CONFLICT_REPORT")
        b_conflict = await recv_until(ws_b, "CONFLICT_REPORT")
        check(
            "alice received CONFLICT_REPORT",
            bool(a_conflict),
            a_conflict["payload"].get("category"),
        )
        check(
            "bob received CONFLICT_REPORT",
            bool(b_conflict),
            b_conflict["payload"].get("category"),
        )
        check(
            "category = dependency_breakage",
            a_conflict["payload"].get("category") == "dependency_breakage",
            a_conflict["payload"].get("category", "?"),
        )
        involved = {
            a_conflict["payload"].get("principal_a"),
            a_conflict["payload"].get("principal_b"),
        }
        check(
            "both principals named in conflict",
            involved == {f"user:{alice['user_id']}", f"user:{bob['user_id']}"},
            f"involved={involved}",
        )

        print("\n5. Bob yields → alice sees INTENT_WITHDRAW")
        await ws_b.send(json.dumps({
            "action": "yield_task",
            "intent_id": bob_intent,
            "reason": "polite",
        }))
        a_withdraw = await recv_until(ws_a, "INTENT_WITHDRAW")
        check(
            "alice received INTENT_WITHDRAW from bob",
            a_withdraw["sender"]["principal_id"] == f"user:{bob['user_id']}",
        )

    print("\n\033[32mAll dependency-breakage checks passed ✓\033[0m")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except AssertionError as e:
        print(f"\n\033[31m{e}\033[0m")
        sys.exit(1)
