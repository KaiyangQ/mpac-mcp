#!/usr/bin/env python3
"""Seed the unified internal-beta example project (``notes_app``).

This replaces ``scripts/seed_beta_scenarios.py``'s 4-separate-scenarios
layout with **one coherent toy project** — a tiny note-taking service —
whose import graph is deliberately shaped to exercise every MPAC
scanner path in a single coordinated playbook:

  * ``from pkg import submodule`` + ``submodule.attr()``
        — 0.2.4 speculative-submodule attribute-chain (``api.py`` uses
          ``from notes_app import db`` + ``db.save(...)``).
  * ``from pkg.submodule import symbol``
        — classic 0.2.1 from-import, single or multi-symbol
          (``search.py`` / ``cli.py`` / the rest of ``api.py``).
  * ``import pkg.submodule`` + ``pkg.submodule.attr()``
        — dotted-import wildcard fallback (``exporter.py``; the
          step-5 "don't do this" educational case).

Step-3 hero setup (the "wow" moment):

    Alice:  announces ``notes_app/db.py`` with
            ``symbols=["notes_app.db.save"]``
    Bob:    edits ``api.py``      → api.py uses ``db.save`` via
                                     from-pkg-import-submodule + attr
                                     → PRECISE symbol conflict
    Carol:  edits ``search.py``   → search.py only uses ``db.load``
                                     (never ``db.save``)
                                     → NO conflict, works in peace

Full playbook in ``docs/BETA_EXAMPLE.md``.

Usage::

    # against production
    scripts/seed_example_project.py \\
        --base https://mpac-web.duckdns.org \\
        --email alice@mpac.test \\
        --password mpac-test-2026

    # against a local dev server
    scripts/seed_example_project.py \\
        --base http://127.0.0.1:8001 \\
        --email alice@mpac.test \\
        --password mpac-test-2026

Idempotent at the project level: re-running creates a NEW
timestamped project so testers can rerun for a clean slate. It does
NOT delete older beta projects; that's a separate admin operation.
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


# ── File tree for notes_app ──────────────────────────────────────


# The content of each file is the ACTUAL import-graph-shaping seed
# used by the scanner. These aren't throwaway stubs — the comments
# inside call out *which* MPAC scanner path each file exercises so
# future readers can map files to playbook steps without re-reading
# the docs.

_INIT_PY = '''"""notes_app — a toy note-taking service for MPAC demo.

Files in this package are deliberately shaped to exercise the full
range of MPAC scanner paths in one coherent project. See
``docs/BETA_EXAMPLE.md`` for the 5-step playbook.
"""
'''


_MODELS_PY = '''"""Domain types.

Both ``db.py`` and ``search.py`` import ``Note`` from here. If Alice
reshapes ``Note``, MPAC will flag anyone editing the downstream
layers during the same session.
"""
from dataclasses import dataclass


@dataclass
class User:
    id: int
    email: str
    password_hash: str


@dataclass
class Note:
    id: int
    owner_id: int
    title: str
    body: str
    created_at: str
'''


_DB_PY = '''"""Storage primitives.

The hero file for the symbol-precision demo. Alice announces only
``notes_app.db.save`` in step 3 — the coordinator then computes which
importers actually touch ``save`` (conflict) vs. only ``load``
(no conflict).
"""
from notes_app.models import Note


_STORE: dict[int, Note] = {}


def save(note: Note) -> None:
    """Persist or overwrite a note."""
    _STORE[note.id] = note


def load(note_id: int) -> Note | None:
    """Fetch one note by id, or None if missing."""
    return _STORE.get(note_id)


def delete(note_id: int) -> None:
    """Remove a note; no-op if already gone."""
    _STORE.pop(note_id, None)


def list_all(owner_id: int) -> list[Note]:
    """Return every note belonging to ``owner_id`` (unsorted)."""
    return [n for n in _STORE.values() if n.owner_id == owner_id]
'''


_SEARCH_PY = '''"""Full-text search index.

Import form: ``from notes_app.db import load`` — classic single-symbol
from-import. This file ONLY uses ``load``; it never writes. That's
what makes Carol's step-3 edit to search.py safe while Alice is
changing ``db.save``: their affect-sets are disjoint.
"""
from notes_app.db import load
from notes_app.models import Note


_INDEX: dict[str, list[int]] = {}


def index_note(note: Note) -> None:
    """Add a note's tokens to the inverted index."""
    for tok in note.body.split():
        _INDEX.setdefault(tok.lower(), []).append(note.id)


def query(term: str) -> list[Note]:
    """Look up note_ids for ``term``, then load each."""
    ids = _INDEX.get(term.lower(), [])
    return [n for n in (load(i) for i in ids) if n is not None]
'''


_AUTH_PY = '''"""Password hashing + session primitives.

Kept self-contained so the step-1 scope-overlap demo can let Alice
and Bob both edit this file (on different functions) without any
import-graph side effects. MPAC 0.2.4 still flags scope_overlap at
the file level — symbol precision only applies to
``dependency_breakage``, not same-file edits, by design.
"""
import hashlib
import secrets


_SESSIONS: dict[str, int] = {}


def hash_password(pw: str) -> str:
    """Placeholder hash — Alice swaps in bcrypt in step 1."""
    return hashlib.sha256(pw.encode()).hexdigest()


def verify_password(pw: str, hashed: str) -> bool:
    return hash_password(pw) == hashed


def create_session(user_id: int) -> str:
    """Mint a random session token tied to user_id."""
    sid = secrets.token_urlsafe(16)
    _SESSIONS[sid] = user_id
    return sid


def delete_session(sid: str) -> None:
    """Bob adds an expiry check here in step 1."""
    _SESSIONS.pop(sid, None)
'''


_API_PY = '''"""HTTP handlers — import-form matrix on purpose.

This file exercises THREE distinct scanner paths deliberately:

  * ``from notes_app import db`` + ``db.save(x)``
        0.2.4 speculative-submodule attribute-chain. The hero case.
        Until 0.2.4 this importer was INVISIBLE to the scanner —
        changing ``db.save`` wouldn't flag api.py as affected.
  * ``from notes_app.auth import verify_password, create_session``
        0.2.1 multi-symbol from-import. Clean precision from the
        beginning.
  * ``from notes_app.models import Note``
        Classic single-symbol from-import.
"""
from notes_app import db
from notes_app.auth import verify_password, create_session
from notes_app.models import Note


def create_note(user_id: int, title: str, body: str) -> int:
    """POST /notes — persist and return the new note's id."""
    note = Note(id=_next_id(), owner_id=user_id, title=title,
                body=body, created_at="2026-04-22")
    db.save(note)          # ← the 0.2.4 attr-chain edge for step 3
    return note.id


def login(email: str, password: str, stored_hash: str) -> str:
    """POST /login — verify and mint a session token."""
    if not verify_password(password, stored_hash):
        raise ValueError("bad creds")
    return create_session(1)  # stub user id


def _next_id() -> int:
    # In a real app, an id generator. Here, fine as a stub.
    return 1
'''


_CLI_PY = '''"""Admin CLI — bulk operations against the store.

Import form: ``from notes_app.db import save, load, delete`` — the
most explicit path for the scanner. This file imports ``save``, so
Alice's step-3 change to ``db.save`` will flag cli.py too. That's
by design — it lets us show that the symbol-precision logic is
symmetric across as many importers as match.
"""
from notes_app.db import save, load, delete
from notes_app.models import Note


def bulk_import(rows: list[tuple[int, str, str]]) -> None:
    """Take TSV-style rows and persist each as a note."""
    for rid, title, body in rows:
        save(Note(id=rid, owner_id=0, title=title, body=body,
                  created_at="2026-04-22"))


def purge(note_id: int) -> None:
    """Delete a note by id, if it exists."""
    if load(note_id) is not None:
        delete(note_id)
'''


_EXPORTER_PY = '''"""Export notes to TSV — **intentionally** demonstrates the
dotted-import gotcha (step 5 in BETA_EXAMPLE.md).

Import form here is ``import notes_app.db`` + ``notes_app.db.list_all()``
— the dotted style. The MPAC scanner cannot disambiguate "submodule
access" from "attribute access on the parent package" without
resolving the module graph, so it stays WILDCARD for this file.

Net effect: even when Alice announces ``db.save`` precisely, an edit
to exporter.py will still produce a file-level-fallback conflict
— the scanner has no evidence that this file doesn't touch save.

Recommended fix (and what api.py / cli.py already do): use
``from notes_app import db`` or ``from notes_app.db import list_all``
instead. Both give the scanner enough structure to emit precise
symbols.
"""
import notes_app.db


def export_all(user_id: int, out_path: str) -> int:
    """Dump every note owned by user_id; returns the row count."""
    n = 0
    for _note in notes_app.db.list_all(user_id):
        # Pretend we're writing TSV here.
        n += 1
    return n
'''


FILES: dict[str, str] = {
    "notes_app/__init__.py": _INIT_PY,
    "notes_app/models.py":   _MODELS_PY,
    "notes_app/db.py":       _DB_PY,
    "notes_app/search.py":   _SEARCH_PY,
    "notes_app/auth.py":     _AUTH_PY,
    "notes_app/api.py":      _API_PY,
    "notes_app/cli.py":      _CLI_PY,
    "notes_app/exporter.py": _EXPORTER_PY,
}


# ── Main flow ────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True,
                    help="API base, e.g. https://mpac-web.duckdns.org")
    ap.add_argument("--email", required=True,
                    help="Owner account (pre-seeded; typically alice@mpac.test)")
    ap.add_argument("--password", required=True)
    ap.add_argument("--project-prefix", default="notes-app-demo",
                    help="Project name prefix; timestamp suffix is added.")
    ap.add_argument("--invite-count", type=int, default=3,
                    help="How many distinct invite codes to mint "
                         "(default 3 — one per expected beta tester).")
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

    print(f"\nSeeding {len(FILES)} files…")
    for path, content in FILES.items():
        _http("PUT", args.base,
              f"/api/projects/{pid}/files/content",
              {"path": path, "content": content},
              token=token)
        print(f"  + {path}")

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
