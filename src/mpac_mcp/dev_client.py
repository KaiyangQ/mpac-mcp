"""Small helper process for Milestone 0 sidecar validation."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

import websockets

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _compat import ensure_local_mpac_import
else:
    from ._compat import ensure_local_mpac_import

ensure_local_mpac_import()

from mpac_protocol.core.models import Scope
from mpac_protocol.core.participant import Participant


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Milestone 0 demo client")
    parser.add_argument("--uri", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--objective")
    parser.add_argument("--file")
    parser.add_argument("--impact-file", action="append", default=[])
    parser.add_argument("--roles", default="contributor")
    parser.add_argument("--goodbye-disposition", default="withdraw")
    parser.add_argument("--hold-sec", type=float, default=4.0)
    return parser


async def run_client(args: argparse.Namespace) -> None:
    roles = [role.strip() for role in args.roles.split(",") if role.strip()]
    participant = Participant(
        principal_id=f"agent:{args.name}",
        principal_type="agent",
        display_name=args.name,
        roles=roles or ["contributor"],
        capabilities=[
            "intent.broadcast",
            "intent.withdraw",
            "intent.claim",
            "conflict.ack",
            "conflict.escalate",
            "conflict.resolve",
        ],
    )
    intent_id = f"intent-{args.name.lower()}-demo"

    async with websockets.connect(args.uri) as ws:
        await ws.send(json.dumps(participant.hello(args.session_id)))
        await asyncio.wait_for(ws.recv(), timeout=2.0)

        announced = False
        if args.objective and args.file:
            extensions = {"impact": args.impact_file} if args.impact_file else None
            msg = participant.announce_intent(
                args.session_id,
                intent_id,
                args.objective,
                Scope(kind="file_set", resources=[args.file], extensions=extensions),
            )
            await ws.send(json.dumps(msg))
            announced = True
        await asyncio.sleep(args.hold_sec)
        active_intents = [intent_id] if announced else None
        await ws.send(json.dumps(
            participant.goodbye(
                args.session_id,
                reason="milestone0_done",
                active_intents=active_intents,
                intent_disposition=args.goodbye_disposition,
            )
        ))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    asyncio.run(run_client(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
