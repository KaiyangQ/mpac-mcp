#!/usr/bin/env python3
"""End-to-end demo driver for the MPAC web-app.

Provisions four accounts in a fresh project — two for the human to log
in as (Alice, Bob) and two "puppet" users (Carol, Dave) the script
controls — then drives the puppets through scripted scenarios via the
same browser-WS protocol the UI uses (begin_task / yield_task).

The split keeps the human's browser tabs alive: the coordinator dedups
participants by principal_id, so a script connecting as the same user
the browser is logged in as would force the browser tab to disconnect.
With puppets, every browser tab just sees Carol/Dave doing things.

Usage:
    # one-time provisioning (idempotent — re-runs reuse existing accounts)
    scripts/demo_driver.py setup

    # scenarios (each connects WS, sends actions, prints messages, closes)
    scripts/demo_driver.py announce              # Carol announces on db.py
    scripts/demo_driver.py conflict              # Carol + Dave overlap
    scripts/demo_driver.py full --delay 3        # full scripted demo
    scripts/demo_driver.py reset                 # reset files to seed

Creds + project_id are persisted to /tmp/mpac_demo_creds.json so each
subcommand can load them without re-asking. Override via --creds-file.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import websockets

DEFAULT_CREDS = Path("/tmp/mpac_demo_creds.json")
DEFAULT_BASE = "http://127.0.0.1:8001"
DEFAULT_FILES = ["notes_app/db.py"]

# Four accounts: 2 humans + 2 puppets. dev-001..dev-004 must be in
# MPAC_WEB_INVITE_CODES at API startup (we ship 5 by convention).
ACCOUNTS = {
    "alice":  {"email": "alice@demo.local",  "password": "alice-pw-1",  "display": "Alice",  "invite": "dev-001"},
    "bob":    {"email": "bob@demo.local",    "password": "bob-pw-1",    "display": "Bob",    "invite": "dev-002"},
    "carol":  {"email": "carol@demo.local",  "password": "carol-pw-1",  "display": "Carol",  "invite": "dev-003"},
    "dave":   {"email": "dave@demo.local",   "password": "dave-pw-1",   "display": "Dave",   "invite": "dev-004"},
}


# ── tiny HTTP helper ───────────────────────────────────────────────

def http(method: str, base: str, path: str,
         body: dict | None = None, token: str | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{base}{path}", data=data,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        raise SystemExit(f"{method} {path} → {e.code}: {body_text}")


def register_or_login(base: str, acct: dict) -> dict:
    """Register if invite still valid; otherwise login. Idempotent."""
    try:
        return http("POST", base, "/api/register", {
            "email": acct["email"],
            "password": acct["password"],
            "display_name": acct["display"],
            "invite_code": acct["invite"],
        })
    except SystemExit as e:
        msg = str(e)
        if "Email already registered" in msg or "already" in msg.lower():
            return http("POST", base, "/api/login",
                        {"email": acct["email"], "password": acct["password"]})
        raise


# ── creds I/O ──────────────────────────────────────────────────────

def save_creds(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2))


def load_creds(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(
            f"No creds file at {path}. Run `demo_driver.py setup` first."
        )
    return json.loads(path.read_text())


# ── setup ──────────────────────────────────────────────────────────

def cmd_setup(args: argparse.Namespace) -> None:
    base = args.base
    print(f"Setting up 4 accounts on {base}…")
    accounts: dict[str, dict] = {}
    for key, acct in ACCOUNTS.items():
        info = register_or_login(base, acct)
        accounts[key] = {
            "user_id": info["user_id"],
            "email": acct["email"],
            "password": acct["password"],
            "display": acct["display"],
            "token": info["token"],
        }
        print(f"  {acct['display']:6s} user_id={info['user_id']}")

    project_name = f"demo-{uuid.uuid4().hex[:6]}"
    proj = http("POST", base, "/api/projects",
                {"name": project_name}, token=accounts["alice"]["token"])
    pid = proj["id"]
    print(f"\nCreated project id={pid} name={project_name}")
    print(f"  session_id={proj['session_id']}")

    # Mint one invite per non-owner, accept on their behalf.
    for key in ("bob", "carol", "dave"):
        invite = http("POST", base, f"/api/projects/{pid}/invite",
                      {"roles": ["contributor"]},
                      token=accounts["alice"]["token"])
        http("POST", base, "/api/invites/accept",
             {"invite_code": invite["invite_code"]},
             token=accounts[key]["token"])
        print(f"  {accounts[key]['display']} accepted invite to project {pid}")

    print("\nSeeding notes_app files…")
    http("POST", base, f"/api/projects/{pid}/reset-to-seed",
         token=accounts["alice"]["token"])

    creds = {
        "base": base,
        "ws_base": args.ws_base or base.replace("http", "ws", 1),
        "project_id": pid,
        "session_id": proj["session_id"],
        "accounts": accounts,
    }
    save_creds(args.creds_file, creds)

    print("\n" + "=" * 64)
    print(f"  Browse to:    http://localhost:3000/projects/{pid}")
    print(f"  Log in as:    alice@demo.local / alice-pw-1   (Alice — owner)")
    print(f"           or:  bob@demo.local   / bob-pw-1     (Bob)")
    print(f"  Script puppets:  Carol + Dave (driven by demo_driver.py)")
    print(f"  Creds saved:  {args.creds_file}")
    print("=" * 64)


# ── WS plumbing ────────────────────────────────────────────────────

async def open_ws(creds: dict, actor: str):
    """Open a browser-protocol WS for `actor` and drain SESSION_INFO."""
    if actor not in creds["accounts"]:
        raise ValueError(f"unknown actor {actor!r}; "
                         f"have {list(creds['accounts'])}")
    token = creds["accounts"][actor]["token"]
    pid = creds["project_id"]
    url = f"{creds['ws_base']}/ws/session/{pid}?token={token}"
    ws = await websockets.connect(url)

    async def _drain_until_session_info():
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get("message_type") == "SESSION_INFO":
                return
    await asyncio.wait_for(_drain_until_session_info(), timeout=3.0)
    return ws


async def begin_task(ws, intent_id: str, files: list[str], objective: str):
    await ws.send(json.dumps({
        "action": "begin_task",
        "intent_id": intent_id,
        "objective": objective,
        "files": files,
    }))


async def yield_task(ws, intent_id: str, reason: str = "demo_yield"):
    await ws.send(json.dumps({
        "action": "yield_task",
        "intent_id": intent_id,
        "reason": reason,
    }))


async def collect(ws, label: str, duration: float) -> list[dict]:
    """Drain incoming messages for `duration`s, printing + collecting them."""
    seen: list[dict] = []
    end = asyncio.get_event_loop().time() + duration

    async def _loop():
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            seen.append(msg)
            t = msg.get("message_type", "?")
            sender = msg.get("sender", {}).get("display_name") \
                or msg.get("sender", {}).get("principal_id", "?")
            extra = ""
            if t == "INTENT_ANNOUNCE":
                files = msg.get("payload", {}).get("scope", {}).get("resources", [])
                extra = f"  files={files}"
            elif t == "CONFLICT_REPORT":
                p = msg.get("payload", {})
                extra = f"  category={p.get('category')!r} principals={p.get('principal_a')}↔{p.get('principal_b')}"
            elif t == "INTENT_WITHDRAW":
                extra = f"  reason={msg.get('payload', {}).get('reason')!r}"
            print(f"  [{label:5s}] ← {t}  from={sender}{extra}")
    try:
        remaining = end - asyncio.get_event_loop().time()
        if remaining > 0:
            await asyncio.wait_for(_loop(), timeout=remaining)
    except asyncio.TimeoutError:
        pass
    return seen


# ── scenarios ──────────────────────────────────────────────────────

async def _scenario_announce(creds, files, hold):
    ws = await open_ws(creds, "carol")
    intent_id = f"intent-carol-{uuid.uuid4().hex[:6]}"
    print(f"\n→ Carol announces intent {intent_id} on {files}")
    await begin_task(ws, intent_id, files, "Carol editing")
    await collect(ws, "carol", hold)
    await ws.close()
    print("\n(Carol's WS closed; the coordinator broadcasts a withdraw on goodbye.)")


async def _scenario_conflict(creds, files, delay):
    ws_c = await open_ws(creds, "carol")
    ws_d = await open_ws(creds, "dave")
    intent_c = f"intent-carol-{uuid.uuid4().hex[:6]}"
    intent_d = f"intent-dave-{uuid.uuid4().hex[:6]}"

    print(f"\n→ Carol announces on {files}")
    await begin_task(ws_c, intent_c, files, "Carol editing db.py")
    await asyncio.gather(
        collect(ws_c, "carol", delay),
        collect(ws_d, "dave", delay),
    )

    print(f"\n→ Dave announces SAME files (overlap should fire CONFLICT_REPORT)")
    await begin_task(ws_d, intent_d, files, "Dave also editing db.py")
    await asyncio.gather(
        collect(ws_c, "carol", delay),
        collect(ws_d, "dave", delay),
    )

    await ws_c.close()
    await ws_d.close()


async def _scenario_full(creds, files, delay):
    ws_c = await open_ws(creds, "carol")
    ws_d = await open_ws(creds, "dave")
    intent_c = f"intent-carol-{uuid.uuid4().hex[:6]}"
    intent_d = f"intent-dave-{uuid.uuid4().hex[:6]}"

    print(f"\n[1/3] Carol announces on {files}  → WHO'S WORKING shows Carol active")
    await begin_task(ws_c, intent_c, files, "Carol editing db.py")
    await asyncio.gather(
        collect(ws_c, "carol", delay),
        collect(ws_d, "dave", delay),
    )

    print(f"\n[2/3] Dave announces SAME file → CONFLICTS panel populates")
    await begin_task(ws_d, intent_d, files, "Dave also editing db.py")
    await asyncio.gather(
        collect(ws_c, "carol", delay),
        collect(ws_d, "dave", delay),
    )

    print(f"\n[3/3] Dave yields → conflict clears, Carol keeps her intent")
    await yield_task(ws_d, intent_d, "polite")
    await asyncio.gather(
        collect(ws_c, "carol", delay),
        collect(ws_d, "dave", delay),
    )

    await ws_c.close()
    await ws_d.close()
    print("\nDone.")


# ── argparse wiring ────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--base", default=DEFAULT_BASE,
                   help="API base URL (default %(default)s)")
    p.add_argument("--ws-base", default=None,
                   help="WS base; defaults to base with http→ws")
    p.add_argument("--creds-file", type=Path, default=DEFAULT_CREDS,
                   help="Where to read/write creds (default %(default)s)")

    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="Provision 4 accounts + project")

    s = sub.add_parser("announce", help="Carol announces an intent")
    s.add_argument("--files", nargs="+", default=DEFAULT_FILES)
    s.add_argument("--hold", type=float, default=2.5)

    s = sub.add_parser("conflict", help="Carol + Dave overlap on same files")
    s.add_argument("--files", nargs="+", default=DEFAULT_FILES)
    s.add_argument("--delay", type=float, default=2.5)

    s = sub.add_parser("full", help="announce → conflict → withdraw")
    s.add_argument("--files", nargs="+", default=DEFAULT_FILES)
    s.add_argument("--delay", type=float, default=2.5)

    sub.add_parser("reset", help="POST /reset-to-seed")
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.cmd == "setup":
        cmd_setup(args)
        return 0

    creds = load_creds(args.creds_file)
    if args.cmd == "announce":
        asyncio.run(_scenario_announce(creds, args.files, args.hold))
    elif args.cmd == "conflict":
        asyncio.run(_scenario_conflict(creds, args.files, args.delay))
    elif args.cmd == "full":
        asyncio.run(_scenario_full(creds, args.files, args.delay))
    elif args.cmd == "reset":
        http("POST", creds["base"],
             f"/api/projects/{creds['project_id']}/reset-to-seed",
             token=creds["accounts"]["alice"]["token"])
        print(f"  reset project {creds['project_id']} to seed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
