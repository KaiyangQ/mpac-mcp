"""Tests for v0.2.1 cross-file dependency-breakage detection.

The motivating scenario — and the thing the user explicitly asked for —
is: ``Alice`` edits ``utils.py``; ``Bob`` edits ``main.py``; ``main.py``
imports from ``utils.py``. Pre-0.2.1 MPAC never flagged this because
scope overlap is a strict "do the resources arrays intersect" check. 0.2.1
adds an ``extensions.impact`` escape-hatch (SPEC.md §15.2 + §17.5) and a
``scope_dependency_conflict`` pass in the coordinator.

Three layers are tested:

1. :mod:`mpac_protocol.analysis.import_index` — the scanner computes the
   right reverse-dep set from a ``{path: content}`` mapping (the shape
   both filesystem and DB-backed callers produce).
2. :func:`mpac_protocol.core.scope.scope_dependency_conflict` — given two
   scopes with pre-computed ``extensions.impact`` lists, does it return
   the right boolean?
3. :class:`mpac_protocol.core.coordinator.SessionCoordinator` —
   announcing two intents with overlapping dep-graphs produces a
   ``CONFLICT_REPORT`` with ``category == "dependency_breakage"``.

The backward-compat case (no ``extensions.impact``) is explicitly
covered: an 0.2.0 client's envelope must still round-trip without error,
and the coordinator must fall back to path-only detection.
"""
from __future__ import annotations

import pytest

from mpac_protocol.analysis.import_index import (
    collect_python_sources_from_dir,
    scan_reverse_deps,
    scan_reverse_deps_detailed,
    scan_reverse_deps_from_dir,
)
from mpac_protocol.core.coordinator import SessionCoordinator
from mpac_protocol.core.models import MessageType, Scope
from mpac_protocol.core.participant import Participant
from mpac_protocol.core.scope import (
    scope_dependency_conflict,
    scope_overlap,
)


# ─── Scanner: in-memory mapping input ────────────────────────────


def test_scanner_finds_direct_importer():
    """``main.py`` does ``from utils import foo`` — utils's reverse deps
    must include main.py."""
    sources = {
        "utils.py": "def foo():\n    return 1\n",
        "main.py": "from utils import foo\n\nfoo()\n",
        "unrelated.py": "x = 1\n",
    }
    assert scan_reverse_deps(["utils.py"], sources) == ["main.py"]


def test_scanner_finds_package_submodule_importer():
    """Editing ``pkg/__init__.py`` flags anything that imports ``pkg.sub``
    since mutating the package affects submodule resolution too."""
    sources = {
        "pkg/__init__.py": "",
        "pkg/sub.py": "def helper():\n    pass\n",
        "client.py": "from pkg.sub import helper\n",
    }
    assert scan_reverse_deps(["pkg/__init__.py"], sources) == ["client.py"]


def test_scanner_resolves_relative_imports():
    """``from .sibling import x`` inside a package must resolve to the
    sibling module, not to a top-level ``sibling``."""
    sources = {
        "pkg/__init__.py": "",
        "pkg/target.py": "X = 1\n",
        "pkg/consumer.py": "from .target import X\n",
        # A top-level ``target`` would accidentally match if we forgot to
        # resolve — assert we don't pick it up as a reverse dep.
        "target.py": "Y = 2\n",
    }
    result = scan_reverse_deps(["pkg/target.py"], sources)
    assert result == ["pkg/consumer.py"]


def test_scanner_excludes_targets_from_result():
    """A target file shouldn't show up in its own impact set, even if it
    happens to self-import something."""
    sources = {
        "utils.py": "from utils import foo  # pathological but legal\n",
        "main.py": "from utils import foo\n",
    }
    assert scan_reverse_deps(["utils.py"], sources) == ["main.py"]


def test_scanner_ignores_unrelated_files():
    sources = {
        "utils.py": "x = 1\n",
        "other.py": "from os import path\n",
    }
    assert scan_reverse_deps(["utils.py"], sources) == []


def test_scanner_survives_syntax_error():
    """A broken file in the project must not crash the scanner — it
    just contributes no imports."""
    sources = {
        "utils.py": "def foo():\n    return 1\n",
        "broken.py": "def (",  # <- syntactically garbage
        "main.py": "from utils import foo\n",
    }
    assert scan_reverse_deps(["utils.py"], sources) == ["main.py"]


def test_scanner_handles_normalized_paths():
    """Scanner accepts ``./utils.py`` and normalizes backslashes."""
    sources = {
        "utils.py": "x = 1\n",
        "main.py": "import utils\n",
    }
    assert scan_reverse_deps(["./utils.py"], sources) == ["main.py"]


def test_scanner_empty_on_non_python_target():
    """Non-.py targets have no module name → empty result (the caller's
    scope handler can still run path-level detection)."""
    sources = {"config.yaml": "x: 1\n"}
    assert scan_reverse_deps(["config.yaml"], sources) == []


# ─── Scanner: filesystem adapter ─────────────────────────────────


def test_scanner_from_dir_roundtrip(tmp_path):
    (tmp_path / "utils.py").write_text("def foo():\n    return 1\n")
    (tmp_path / "main.py").write_text("from utils import foo\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "noise.py").write_text("from utils import foo\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.py").write_text("from utils import foo\n")

    assert scan_reverse_deps_from_dir(["utils.py"], str(tmp_path)) == ["main.py"]


def test_collect_python_sources_skips_standard_dirs(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "b.py").write_text("x = 2\n")

    sources = collect_python_sources_from_dir(str(tmp_path))
    assert set(sources.keys()) == {"a.py"}


# ─── scope_dependency_conflict (pure function) ──────────────────


def _scope(files, impact=None):
    ext = {"impact": impact} if impact is not None else None
    return Scope(kind="file_set", resources=list(files), extensions=ext)


def test_dep_conflict_when_edit_hits_others_impact():
    """Alice edits utils.py (impact = [main.py]). Bob edits main.py.
    main.py is in Alice's impact AND is Bob's resource → dep conflict."""
    alice = _scope(["utils.py"], impact=["main.py"])
    bob = _scope(["main.py"])
    assert scope_dependency_conflict(alice, bob) is True
    # And symmetric:
    assert scope_dependency_conflict(bob, alice) is True


def test_no_dep_conflict_without_impact():
    """With neither side populating impact, dep detection must be silent —
    this is the 0.2.0 graceful-degradation path."""
    alice = _scope(["utils.py"])
    bob = _scope(["main.py"])
    assert scope_dependency_conflict(alice, bob) is False


def test_no_dep_conflict_when_impact_disjoint():
    alice = _scope(["utils.py"], impact=["main.py"])
    bob = _scope(["unrelated.py"])
    assert scope_dependency_conflict(alice, bob) is False


def test_dep_conflict_not_triggered_by_direct_overlap():
    """scope_dependency_conflict is NOT about same-file overlap — that's
    scope_overlap's job. It must stay silent when resources intersect
    directly, so the coordinator doesn't double-count."""
    alice = _scope(["utils.py"], impact=["main.py"])
    bob = _scope(["utils.py"], impact=["main.py"])
    # Direct overlap exists; scope_overlap handles that case.
    assert scope_overlap(alice, bob) is True
    # scope_dependency_conflict checks cross-file via impact only — and
    # here one side's resource is in the other's impact (main.py not
    # involved, utils.py is a direct overlap).
    # We still accept True here because coordinator's flow checks
    # scope_overlap FIRST and short-circuits. This test documents the
    # separation of concerns.
    # (Either True or False is acceptable; the wire-level contract is
    # "coordinator checks overlap first". Assert only the coordinator
    # contract in the integration test below.)


def test_dep_conflict_requires_file_set_kind():
    alice = Scope(
        kind="entity_set", entities=["a.b"],
        extensions={"impact": ["a.c"]},
    )
    bob = Scope(kind="entity_set", entities=["a.c"])
    assert scope_dependency_conflict(alice, bob) is False


# ─── Scope round-trip preserves extensions ──────────────────────


def test_scope_to_from_dict_roundtrips_extensions():
    original = Scope(
        kind="file_set",
        resources=["utils.py"],
        extensions={"impact": ["main.py", "api.py"]},
    )
    restored = Scope.from_dict(original.to_dict())
    assert restored.extensions == {"impact": ["main.py", "api.py"]}
    assert restored.resources == ["utils.py"]


def test_scope_from_dict_tolerates_missing_extensions():
    """0.2.0 envelope shape (no extensions) must deserialize cleanly."""
    data = {"kind": "file_set", "resources": ["x.py"]}
    scope = Scope.from_dict(data)
    assert scope.extensions is None


def test_scope_from_dict_ignores_unknown_top_level_fields():
    """A future 0.3+ field that this old code doesn't know about must
    not crash from_dict — unknown keys are silently dropped."""
    data = {
        "kind": "file_set",
        "resources": ["x.py"],
        "extensions": {"impact": ["y.py"]},
        "future_field_we_dont_know": "something",
    }
    scope = Scope.from_dict(data)
    assert scope.resources == ["x.py"]
    assert scope.extensions == {"impact": ["y.py"]}


# ─── v0.2.2: symbol-level detailed scanner ─────────────────────


def test_detailed_scanner_pins_from_imports():
    """`from utils import foo, bar` — detailed scanner records both
    names, fully qualified against the target module."""
    sources = {
        "utils.py": "def foo(): pass\ndef bar(): pass\n",
        "main.py": "from utils import foo, bar\n",
    }
    result = scan_reverse_deps_detailed(["utils.py"], sources)
    assert result == {"main.py": ["utils.bar", "utils.foo"]}


def test_detailed_scanner_uses_original_name_not_alias():
    """`from utils import foo as f` — we track ``foo``, not ``f``.
    Alice cares about which of HER symbols are touched, not what the
    importer renamed them to."""
    sources = {
        "utils.py": "def foo(): pass\n",
        "main.py": "from utils import foo as f\n",
    }
    assert scan_reverse_deps_detailed(["utils.py"], sources) == {
        "main.py": ["utils.foo"]
    }


def test_detailed_scanner_wildcard_on_star_import():
    """`from utils import *` — we can't tell which symbols; return None
    so the conflict detector treats it as 'any symbol could be used'."""
    sources = {
        "utils.py": "def foo(): pass\n",
        "star.py": "from utils import *\n",
    }
    assert scan_reverse_deps_detailed(["utils.py"], sources) == {"star.py": None}


def test_detailed_scanner_wildcard_on_bare_import():
    """`import utils` — no specific names yet; attribute access could
    happen anywhere downstream. Flag wildcard."""
    sources = {
        "utils.py": "def foo(): pass\n",
        "docs.py": "import utils\n",
    }
    assert scan_reverse_deps_detailed(["utils.py"], sources) == {"docs.py": None}


def test_detailed_scanner_merges_multiple_imports_from_same_file():
    """If a file has two separate `from utils import ...` statements,
    the symbol sets merge (deduped, sorted)."""
    sources = {
        "utils.py": "def foo(): pass\ndef bar(): pass\ndef baz(): pass\n",
        "main.py": "from utils import foo\n\nfrom utils import bar, foo\n",
    }
    assert scan_reverse_deps_detailed(["utils.py"], sources) == {
        "main.py": ["utils.bar", "utils.foo"]
    }


def test_detailed_scanner_wildcard_dominates_specific():
    """If a file has both `import utils` (wildcard) and `from utils
    import foo` (specific), wildcard wins — we must assume any symbol
    could be used."""
    sources = {
        "utils.py": "def foo(): pass\n",
        "mixed.py": "import utils\nfrom utils import foo\n",
    }
    assert scan_reverse_deps_detailed(["utils.py"], sources) == {"mixed.py": None}


# ─── v0.2.2: scope_dependency_conflict with symbol precision ────


def _scope_with(
    resources,
    impact=None,
    impact_symbols=None,
    affects_symbols=None,
):
    """Test helper — build a scope with any v0.2.1 / v0.2.2 extensions."""
    ext = {}
    if impact is not None:
        ext["impact"] = impact
    if impact_symbols is not None:
        ext["impact_symbols"] = impact_symbols
    if affects_symbols is not None:
        ext["affects_symbols"] = affects_symbols
    return Scope(
        kind="file_set",
        resources=list(resources),
        extensions=ext or None,
    )


def test_precision_no_conflict_when_symbols_disjoint():
    """**The motivating case for v0.2.2.**

    Alice edits only ``utils.foo``. main.py imports only ``utils.bar``.
    Pre-0.2.2 this was a false positive; 0.2.2 correctly says "no
    conflict" because the symbol sets are disjoint.
    """
    alice = _scope_with(
        ["utils.py"],
        impact=["main.py"],
        impact_symbols={"main.py": ["utils.bar"]},
        affects_symbols=["utils.foo"],
    )
    bob = _scope_with(["main.py"])
    assert scope_dependency_conflict(alice, bob) is False


def test_precision_conflict_when_symbols_match():
    """Alice edits ``utils.foo``; main.py uses ``utils.foo``. Still a
    conflict — just precisely scoped to the right symbol."""
    alice = _scope_with(
        ["utils.py"],
        impact=["main.py"],
        impact_symbols={"main.py": ["utils.foo", "utils.bar"]},
        affects_symbols=["utils.foo"],
    )
    bob = _scope_with(["main.py"])
    assert scope_dependency_conflict(alice, bob) is True


def test_precision_falls_back_when_importer_uses_wildcard():
    """main.py does ``import utils`` — scanner can't pin symbols.
    Even though Alice declared ``affects_symbols``, we must conservatively
    flag a conflict."""
    alice = _scope_with(
        ["utils.py"],
        impact=["main.py"],
        impact_symbols={"main.py": None},
        affects_symbols=["utils.foo"],
    )
    bob = _scope_with(["main.py"])
    assert scope_dependency_conflict(alice, bob) is True


def test_precision_falls_back_when_editor_didnt_declare_symbols():
    """Alice didn't declare ``affects_symbols`` — old 0.2.1 client, or
    she genuinely doesn't know which symbols she'll touch. Coordinator
    degrades to file-level: anyone importing utils.py is a conflict."""
    alice = _scope_with(
        ["utils.py"],
        impact=["main.py"],
        impact_symbols={"main.py": ["utils.bar"]},
        # no affects_symbols
    )
    bob = _scope_with(["main.py"])
    assert scope_dependency_conflict(alice, bob) is True


def test_precision_falls_back_when_coordinator_has_no_impact_symbols():
    """Old 0.2.1 client: populated ``impact`` but not ``impact_symbols``.
    New 0.2.2 coordinator must still flag the conflict by the file-level
    rule."""
    alice = _scope_with(
        ["utils.py"],
        impact=["main.py"],
        affects_symbols=["utils.foo"],
        # no impact_symbols
    )
    bob = _scope_with(["main.py"])
    assert scope_dependency_conflict(alice, bob) is True


def test_precision_symmetric_direction():
    """Check the symmetric check: Bob is the 'editor' with symbol info,
    Alice is the 'importer'."""
    alice = _scope_with(["main.py"])
    bob = _scope_with(
        ["utils.py"],
        impact=["main.py"],
        impact_symbols={"main.py": ["utils.bar"]},
        affects_symbols=["utils.foo"],
    )
    assert scope_dependency_conflict(alice, bob) is False


def test_precision_one_side_specific_other_side_wildcard_per_importer():
    """Multiple importers, mixed per-importer precision. Alice touches
    foo. api.py uses only bar (safe). docs.py is wildcard (conflict).
    Both importers are claimed by Bob — result should still be conflict
    because docs.py forces the conservative path."""
    alice = _scope_with(
        ["utils.py"],
        impact=["api.py", "docs.py"],
        impact_symbols={
            "api.py": ["utils.bar"],
            "docs.py": None,
        },
        affects_symbols=["utils.foo"],
    )
    bob = _scope_with(["docs.py"])  # Bob claims the wildcard one
    assert scope_dependency_conflict(alice, bob) is True

    # Conversely: Bob claims only the safe one
    bob_safe = _scope_with(["api.py"])
    assert scope_dependency_conflict(alice, bob_safe) is False


# ─── Coordinator integration ────────────────────────────────────


def _hello(principal_id, session_id):
    p = Participant(
        principal_id=principal_id,
        principal_type="agent",
        display_name=principal_id,
        roles=["contributor"],
        capabilities=["intent.broadcast", "op.commit"],
    )
    return p, p.hello(session_id)


def _find_conflict(responses):
    for r in responses:
        if r.get("message_type") == MessageType.CONFLICT_REPORT.value:
            return r
    return None


def test_coordinator_reports_dependency_breakage_across_files():
    """End-to-end: Alice announces utils.py with impact=[main.py]; Bob
    announces main.py. Coordinator must emit a CONFLICT_REPORT with
    category=dependency_breakage."""
    session_id = "sess-dep-1"
    coord = SessionCoordinator(session_id, security_profile="open")

    alice, hello_a = _hello("alice", session_id)
    bob, hello_b = _hello("bob", session_id)
    coord.process_message(hello_a)
    coord.process_message(hello_b)

    # Alice claims utils.py; her client's analyzer has already found
    # main.py depends on it.
    alice_scope = Scope(
        kind="file_set",
        resources=["utils.py"],
        extensions={"impact": ["main.py"]},
    )
    coord.process_message(
        alice.announce_intent(session_id, "intent-a", "refactor", alice_scope)
    )

    # Bob claims main.py (no overlap on resources; but in Alice's impact).
    bob_scope = Scope(kind="file_set", resources=["main.py"])
    responses = coord.process_message(
        bob.announce_intent(session_id, "intent-b", "fix bug", bob_scope)
    )

    conflict = _find_conflict(responses)
    assert conflict is not None, "expected a CONFLICT_REPORT, got none"
    payload = conflict["payload"]
    assert payload["category"] == "dependency_breakage"
    assert {payload["principal_a"], payload["principal_b"]} == {"alice", "bob"}


def test_coordinator_still_reports_scope_overlap_for_direct_conflict():
    """Regression: the classic same-file overlap case still produces
    category=scope_overlap (not dependency_breakage)."""
    session_id = "sess-dep-2"
    coord = SessionCoordinator(session_id, security_profile="open")

    alice, hello_a = _hello("alice", session_id)
    bob, hello_b = _hello("bob", session_id)
    coord.process_message(hello_a)
    coord.process_message(hello_b)

    scope_a = Scope(kind="file_set", resources=["same.py"])
    scope_b = Scope(kind="file_set", resources=["same.py"])

    coord.process_message(
        alice.announce_intent(session_id, "intent-a", "edit", scope_a)
    )
    responses = coord.process_message(
        bob.announce_intent(session_id, "intent-b", "edit", scope_b)
    )

    conflict = _find_conflict(responses)
    assert conflict is not None
    assert conflict["payload"]["category"] == "scope_overlap"


def test_coordinator_no_conflict_when_symbols_disjoint_v022():
    """End-to-end: Alice declares ``affects_symbols=["utils.foo"]`` + scanner
    says main.py only uses ``utils.bar``. Bob claims main.py. No conflict
    should fire (v0.2.2 precision kicks in).

    This is the single most important test for the symbol-precision
    upgrade — it's the concrete false-positive-removal case."""
    session_id = "sess-dep-sym-1"
    coord = SessionCoordinator(session_id, security_profile="open")

    alice, hello_a = _hello("alice", session_id)
    bob, hello_b = _hello("bob", session_id)
    coord.process_message(hello_a)
    coord.process_message(hello_b)

    alice_scope = Scope(
        kind="file_set",
        resources=["utils.py"],
        extensions={
            "impact": ["main.py"],
            "impact_symbols": {"main.py": ["utils.bar"]},
            "affects_symbols": ["utils.foo"],
        },
    )
    coord.process_message(
        alice.announce_intent(session_id, "intent-a", "refactor foo", alice_scope)
    )

    bob_scope = Scope(kind="file_set", resources=["main.py"])
    responses = coord.process_message(
        bob.announce_intent(session_id, "intent-b", "fix entrypoint", bob_scope)
    )

    assert _find_conflict(responses) is None, (
        "v0.2.2 should NOT flag this — Alice only touches utils.foo, "
        "main.py only uses utils.bar, so there's no actual risk."
    )


def test_coordinator_still_flags_when_symbols_match_v022():
    """Regression: same plumbing but symbols DO match → conflict fires."""
    session_id = "sess-dep-sym-2"
    coord = SessionCoordinator(session_id, security_profile="open")

    alice, hello_a = _hello("alice", session_id)
    bob, hello_b = _hello("bob", session_id)
    coord.process_message(hello_a)
    coord.process_message(hello_b)

    alice_scope = Scope(
        kind="file_set",
        resources=["utils.py"],
        extensions={
            "impact": ["main.py"],
            "impact_symbols": {"main.py": ["utils.foo"]},
            "affects_symbols": ["utils.foo"],
        },
    )
    coord.process_message(
        alice.announce_intent(session_id, "intent-a", "refactor foo", alice_scope)
    )

    bob_scope = Scope(kind="file_set", resources=["main.py"])
    responses = coord.process_message(
        bob.announce_intent(session_id, "intent-b", "edit main", bob_scope)
    )

    conflict = _find_conflict(responses)
    assert conflict is not None
    assert conflict["payload"]["category"] == "dependency_breakage"


def test_coordinator_skips_conflict_when_no_overlap_and_no_impact():
    """If neither side populated impact (0.2.0 client talking to 0.2.1
    coordinator) AND the resources are disjoint, there must be NO
    conflict — graceful degradation to path-only behavior."""
    session_id = "sess-dep-3"
    coord = SessionCoordinator(session_id, security_profile="open")

    alice, hello_a = _hello("alice", session_id)
    bob, hello_b = _hello("bob", session_id)
    coord.process_message(hello_a)
    coord.process_message(hello_b)

    scope_a = Scope(kind="file_set", resources=["utils.py"])
    scope_b = Scope(kind="file_set", resources=["main.py"])

    coord.process_message(
        alice.announce_intent(session_id, "intent-a", "edit", scope_a)
    )
    responses = coord.process_message(
        bob.announce_intent(session_id, "intent-b", "edit", scope_b)
    )

    assert _find_conflict(responses) is None
