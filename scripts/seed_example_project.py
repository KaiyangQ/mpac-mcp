#!/usr/bin/env python3
"""Seed (or reset) the unified internal-beta example project (``notes_app``).

This replaces ``scripts/seed_beta_scenarios.py``'s 4-separate-scenarios
layout with **one coherent toy project** — a tiny note-taking service —
whose import graph is deliberately shaped to exercise every MPAC
scanner path in a single coordinated playbook. Full playbook in
``docs/BETA_EXAMPLE.md``.

The canonical seed file tree lives server-side in
``web-app/api/seed_data/notes_app.py``; both modes here just hit the
``POST /api/projects/{id}/reset-to-seed`` endpoint to apply it.

Usage::

    # default — create a NEW timestamped project + 3 single-use invites
    scripts/seed_example_project.py \\
        --base https://mpac-web.duckdns.org \\
        --email alice@mpac.test \\
        --password mpac-test-2026

    # reset — keep an EXISTING project's URL/members/invites, only
    # overwrite the 8 canonical files back to seed state
    scripts/seed_example_project.py \\
        --base https://mpac-web.duckdns.org \\
        --email alice@mpac.test \\
        --password mpac-test-2026 \\
        --reset 1

The reset endpoint is also wired to a "Reset" button on the project
page — owners typically click that instead of running this script.
The CLI form is for headless / scripted runs and for the create mode
(which the button can't do).
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.error
import urllib.request
from typing import Optional


def _http(method: str, base: str, path: str, body: Optional[dict] = None,
          token: Optional[str] = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{base}{path}", data=data, headers=headers,
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} → {e.code}: {e.read().decode()}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True,
                    help="API base, e.g. https://mpac-web.duckdns.org")
    ap.add_argument("--email", required=True,
                    help="Owner account (pre-seeded; typically alice@mpac.test)")
    ap.add_argument("--password", required=True)
    ap.add_argument("--reset", type=int, metavar="PROJECT_ID", default=None,
                    help="Skip project creation + invite minting; only "
                         "overwrite the canonical files in PROJECT_ID back "
                         "to seed state. URL, members, and invite codes "
                         "are unchanged.")
    ap.add_argument("--project-prefix", default="notes-app-demo",
                    help="Project name prefix; timestamp suffix is added. "
                         "(Ignored in --reset mode.)")
    ap.add_argument("--invite-count", type=int, default=3,
                    help="How many distinct invite codes to mint "
                         "(default 3 — one per expected beta tester). "
                         "(Ignored in --reset mode.)")
    args = ap.parse_args()

    print(f"Logging in as {args.email}…")
    me = _http("POST", args.base, "/api/login",
               {"email": args.email, "password": args.password})
    token = me["token"]
    print(f"  user_id={me['user_id']} token=<ok>")

    if args.reset is not None:
        pid = args.reset
        print(f"\nResetting project {pid} to seed state…")
        _http("POST", args.base,
              f"/api/projects/{pid}/reset-to-seed",
              token=token)
        print("\n" + "=" * 60)
        print(f"  notes_app demo reset — project {pid}")
        print("=" * 60)
        print(f"  URL: {args.base}/projects/{pid}")
        print()
        print("Files restored to canonical seed state. Project URL,")
        print("members, and invite codes are unchanged.")
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    project_name = f"{args.project_prefix}-{stamp}"
    print(f"\nCreating project {project_name}…")
    proj = _http("POST", args.base, "/api/projects", {"name": project_name},
                 token=token)
    pid = proj["id"]
    sid = proj["session_id"]
    print(f"  project id={pid}  session={sid}")

    print("\nSeeding files via reset-to-seed endpoint…")
    _http("POST", args.base,
          f"/api/projects/{pid}/reset-to-seed",
          token=token)

    print(f"\nMinting {args.invite_count} invite code(s)…")
    invites: list[str] = []
    for _ in range(args.invite_count):
        inv = _http("POST", args.base,
                    f"/api/projects/{pid}/invite",
                    {"roles": ["contributor"]}, token=token)
        invites.append(inv["invite_code"])

    print("\n" + "=" * 60)
    print(f"  notes_app demo ready — project {project_name}")
    print("=" * 60)
    print(f"  URL:          {args.base}/projects/{pid}")
    print(f"  owner:        {args.email}")
    print(f"  session id:   {sid}")
    print(f"  invite codes: (one per tester; single-use)")
    for code in invites:
        print(f"      {code}")
    print()
    print("Next: hand the invite codes out; testers open the URL,")
    print("paste the Connect-Claude one-liner, and follow")
    print("    docs/BETA_EXAMPLE.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
