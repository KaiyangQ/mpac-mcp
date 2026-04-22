"""Seed the internal-beta MPAC demo scenarios into a fresh project.

Creates a project named ``beta-demo-YYYY-MM-DD`` under the Alice test
account (assumed already seeded per BETA_ACCESS.md), populates it with
four scenario file trees documented in ``docs/BETA_SCENARIOS.md``, and
prints an invite code so beta testers can join.

Usage::

    # against production
    scripts/seed_beta_scenarios.py \\
        --base https://mpac-web.duckdns.org \\
        --email alice@mpac.test \\
        --password mpac-test-2026

    # against a local dev server
    scripts/seed_beta_scenarios.py \\
        --base http://127.0.0.1:8001 \\
        --email alice@mpac.test \\
        --password mpac-test-2026

The script is idempotent ON THE PROJECT LEVEL — re-running creates a
NEW project (timestamped), so testers can rerun to get a clean slate.
It does NOT delete old beta projects; clean up manually if needed.

Each scenario lives in its own top-level package (dir + ``__init__.py``)
so Python import semantics work correctly — e.g. inside
``scenario_2_dep_breakage/api.py`` the import is
``from scenario_2_dep_breakage.utils import fetch_data``. The MPAC
scanner resolves these against the target file's module path, so
dep-breakage / symbol detection fires exactly as it would in a real
project.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.error
import urllib.request
from typing import Optional


# ── HTTP glue ─────────────────────────────────────────────────────


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


# ── Scenario file trees ──────────────────────────────────────────

# Each scenario lives in its own package under the project root so
# imports resolve without colliding with the others. Inside each file
# we use fully-qualified imports (``scenario_2_dep_breakage.utils``)
# so the MPAC scanner can walk the graph correctly.

SCENARIOS: dict[str, dict[str, str]] = {
    "scenario_1_same_file": {
        "__init__.py": "",
        "auth.py": (
            "\"\"\"Scenario 1 — Same-file overlap warm-up.\n\n"
            "Two agents both try to edit verify_password / login. Alice's\n"
            "and Bob's intents claim the SAME file; coordinator reports\n"
            "``category=scope_overlap`` (classic case, SPEC.md §15.2.1.1).\n"
            "\"\"\"\n\n"
            "def verify_password(pw: str) -> bool:\n"
            "    # Intentionally dumb; Alice will swap in bcrypt.\n"
            "    return pw == \"admin\"\n\n\n"
            "def login(user: str, pw: str) -> dict:\n"
            "    if not verify_password(pw):\n"
            "        return {\"error\": \"invalid\"}\n"
            "    return {\"token\": \"xyz-\" + user}\n"
        ),
    },
    "scenario_2_dep_breakage": {
        "__init__.py": "",
        "utils.py": (
            "\"\"\"Scenario 2 — Cross-file dependency-breakage.\n\n"
            "Alice refactors utils.py (without declaring specific symbols).\n"
            "Bob touches api.py. No shared files → classical file-level\n"
            "overlap would MISS this. MPAC 0.2.1+ catches it via the import\n"
            "graph: coordinator fires ``category=dependency_breakage``.\n"
            "\"\"\"\n\n"
            "def fetch_data(url: str) -> bytes:\n"
            "    return b\"...\"  # pretend to fetch\n\n\n"
            "def parse_result(raw: bytes) -> dict:\n"
            "    return {\"ok\": True, \"len\": len(raw)}\n"
        ),
        "api.py": (
            "from scenario_2_dep_breakage.utils import fetch_data\n\n\n"
            "def get_users() -> bytes:\n"
            "    return fetch_data(\"/api/users\")\n"
        ),
        "handler.py": (
            "from scenario_2_dep_breakage.utils import parse_result\n\n\n"
            "def handle(raw: bytes) -> dict:\n"
            "    return parse_result(raw)\n"
        ),
    },
    "scenario_3_symbol_precision": {
        "__init__.py": "",
        "utils.py": (
            "\"\"\"Scenario 3 — Symbol-level precision (MPAC 0.2.2 + 0.2.3).\n\n"
            "Alice plans to change ONLY ``fetch`` (declares symbols=\n"
            "[scenario_3_symbol_precision.utils.fetch]). Two other agents\n"
            "touch importers:\n"
            "  - Bob edits main.py, which imports ``fetch``  → CONFLICT\n"
            "  - Carol edits cli.py,  which imports ``parse`` → NO conflict\n"
            "\n"
            "This is the headline demo: Carol keeps working uninterrupted.\n"
            "The conflict card Bob sees should say explicitly:\n"
            "  \"Alice is changing `scenario_3_symbol_precision.utils.fetch`\n"
            "   — affects Bob's `main.py`\"\n"
            "\"\"\"\n\n"
            "def fetch(url: str) -> bytes:\n"
            "    # Slow today; Alice will add a cache here.\n"
            "    return b\"...\"\n\n\n"
            "def parse(text: str) -> dict:\n"
            "    return {\"text\": text}\n"
        ),
        "main.py": (
            "from scenario_3_symbol_precision.utils import fetch\n\n\n"
            "def run() -> bytes:\n"
            "    return fetch(\"/api/x\")\n"
        ),
        "cli.py": (
            "from scenario_3_symbol_precision.utils import parse\n\n\n"
            "def cmd(text: str) -> dict:\n"
            "    return parse(text)\n"
        ),
    },
    "scenario_4_attr_chain": {
        "__init__.py": "",
        "cache.py": (
            "\"\"\"Scenario 4 — Attribute-chain import resolution (MPAC 0.2.3).\n\n"
            "service.py uses ``import cache`` + ``cache.store()`` instead of\n"
            "``from cache import store``. MPAC 0.2.2 would treat this as\n"
            "wildcard (any symbol in cache could be touched). 0.2.3 walks\n"
            "the AST and resolves it to the concrete symbol ``cache.store``.\n"
            "\n"
            "If Alice announces ``symbols=[scenario_4_attr_chain.cache.store]``\n"
            "and Bob touches service.py, the coordinator should fire a\n"
            "conflict — NOT silently drop it because of the wildcard.\n"
            "\"\"\"\n\n"
            "def store(key: str, value) -> None:\n"
            "    pass\n\n\n"
            "def load(key: str):\n"
            "    return None\n"
        ),
        "service.py": (
            "from scenario_4_attr_chain import cache\n\n\n"
            "def save(key: str, value) -> None:\n"
            "    cache.store(key, value)  # attribute-chain access\n"
        ),
        "noop.py": (
            "# Unrelated file — touching this creates NO conflict with\n"
            "# anyone editing scenario_4_attr_chain.cache. Use as a\n"
            "# negative control during the demo.\n"
            "def unrelated() -> int:\n"
            "    return 42\n"
        ),
    },
}


# ── Main flow ────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True,
                    help="API base, e.g. https://mpac-web.duckdns.org")
    ap.add_argument("--email", required=True,
                    help="Owner account (pre-seeded; typically alice@mpac.test)")
    ap.add_argument("--password", required=True)
    ap.add_argument("--project-prefix", default="beta-demo",
                    help="Project name prefix; a timestamp suffix is added "
                         "so re-runs produce fresh projects.")
    ap.add_argument("--invite-count", type=int, default=3,
                    help="How many distinct invite codes to mint "
                         "(default: 3, one per expected beta tester).")
    args = ap.parse_args()

    print(f"Logging in as {args.email}…")
    me = _http("POST", args.base, "/api/login",
               {"email": args.email, "password": args.password})
    token = me["token"]
    print(f"  user_id={me['user_id']} token=<ok>")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    project_name = f"{args.project_prefix}-{stamp}"
    print(f"\nCreating project {project_name}…")
    proj = _http("POST", args.base, "/api/projects", {"name": project_name},
                 token=token)
    pid = proj["id"]
    sid = proj["session_id"]
    print(f"  project id={pid}  session={sid}")

    print(f"\nSeeding {sum(len(f) for f in SCENARIOS.values())} files "
          f"across {len(SCENARIOS)} scenarios…")
    total = 0
    for scenario, files in SCENARIOS.items():
        for filename, content in files.items():
            path = f"{scenario}/{filename}"
            _http("PUT", args.base,
                  f"/api/projects/{pid}/files/content",
                  {"path": path, "content": content},
                  token=token)
            total += 1
            print(f"  + {path}")
    print(f"seeded {total} files")

    print(f"\nMinting {args.invite_count} invite code(s)…")
    invites: list[str] = []
    for _ in range(args.invite_count):
        inv = _http("POST", args.base,
                    f"/api/projects/{pid}/invite",
                    {"roles": ["contributor"]}, token=token)
        invites.append(inv["invite_code"])

    print("\n" + "=" * 60)
    print(f"  beta demo ready  —  project  {project_name}")
    print("=" * 60)
    print(f"  URL:          {args.base}/projects/{pid}")
    print(f"  owner:        {args.email}")
    print(f"  session id:   {sid}")
    print(f"  invite codes: (one per tester; single-use)")
    for code in invites:
        print(f"      {code}")
    print()
    print("Next: hand the invite codes out, have testers run")
    print("    mpac-mcp-claude-setup   (once Claude is connected)")
    print("and point their chat at:")
    print(f"    {args.base}/projects/{pid}")
    print()
    print("Follow docs/BETA_SCENARIOS.md for the four test scripts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
