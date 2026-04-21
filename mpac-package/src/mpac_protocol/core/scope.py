"""Scope overlap detection for MPAC.

Two kinds of conflicts live here:

* ``scope_overlap`` — the classical case where two scopes claim overlapping
  resources (same file, same entity, same task). SPEC.md §15.2.1.1 defines
  this as a MUST: ``file_set`` overlap is *iff* resources intersect.
* ``scope_dependency_conflict`` (v0.2.1, new) — the cross-file case where
  no resources overlap but one scope's edits reach into the other's via an
  import. The coordinator reports these with category ``dependency_breakage``
  (SPEC.md §17.5 already lists this category; v0.2.1 fills in a concrete
  detection rule for it without widening what "overlap" means).
"""
from typing import List
import re

from .models import Scope


def normalize_path(path: str) -> str:
    """Normalize a file path for comparison.

    Steps:
    1. Remove leading ./
    2. Collapse multiple slashes (//)
    3. Remove trailing slashes

    Args:
        path: File path to normalize

    Returns:
        Normalized path
    """
    # Remove leading ./
    if path.startswith("./"):
        path = path[2:]

    # Collapse multiple slashes
    path = re.sub(r'/+', '/', path)

    # Remove trailing slash (except for root /)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    return path


def scope_overlap(a: Scope, b: Scope) -> bool:
    """Detect if two scopes overlap.

    Args:
        a: First scope
        b: Second scope

    Returns:
        True if scopes overlap, False otherwise
    """
    # Different scope kinds: conservative assumption of overlap
    if a.kind != b.kind:
        return True

    # Same kind: check for intersection based on field names
    if a.kind == "file_set":
        # Normalize all paths and check for intersection
        a_items = {normalize_path(item) for item in (a.resources or [])}
        b_items = {normalize_path(item) for item in (b.resources or [])}
        return len(a_items & b_items) > 0

    elif a.kind == "entity_set":
        # Exact string matching for entity sets
        a_items = set(a.entities or [])
        b_items = set(b.entities or [])
        return len(a_items & b_items) > 0

    elif a.kind == "task_set":
        # Exact string matching for task sets
        a_items = set(a.task_ids or [])
        b_items = set(b.task_ids or [])
        return len(a_items & b_items) > 0

    else:
        # Unknown scope kind: conservative True
        return True


def _scope_impact(scope: Scope) -> List[str]:
    """Pull the (possibly empty) cross-file impact list from a scope.

    The impact set lives under ``scope.extensions["impact"]`` by convention
    (see SPEC.md §15.2 extensions escape hatch). We validate shape here so
    junk or legacy payloads degrade to "no impact info" rather than crash.
    """
    if not scope.extensions:
        return []
    impact = scope.extensions.get("impact")
    if not isinstance(impact, list):
        return []
    return [x for x in impact if isinstance(x, str)]


def scope_dependency_conflict(a: Scope, b: Scope) -> bool:
    """Detect a cross-file dependency conflict between two ``file_set`` scopes.

    Returns True when either:

    * a file in ``a.resources`` is reported as impacted by ``b.extensions.impact``
      (i.e. ``b``'s edits reach a file ``a`` is about to touch), or
    * symmetrically, a file in ``b.resources`` appears in ``a.extensions.impact``.

    This function intentionally does NOT flag classic same-file overlap —
    ``scope_overlap`` already owns that case. The caller is expected to
    check ``scope_overlap`` first and only fall back here if no direct
    overlap was found; the coordinator does exactly that.

    Empty or missing ``extensions.impact`` → always False, which is the
    graceful-degradation path for clients that haven't run the analyzer.
    """
    if a.kind != "file_set" or b.kind != "file_set":
        # Cross-kind or non-file scopes don't carry import semantics.
        return False

    a_resources = {normalize_path(r) for r in (a.resources or [])}
    b_resources = {normalize_path(r) for r in (b.resources or [])}
    a_impact = {normalize_path(r) for r in _scope_impact(a)}
    b_impact = {normalize_path(r) for r in _scope_impact(b)}

    # a's edits reach a file b is also claiming? or vice versa?
    return bool((a_impact & b_resources) or (b_impact & a_resources))


def scope_contains(container: Scope, test: Scope) -> bool:
    """Check if *test* scope is fully contained within *container* scope.

    Returns True when every item in *test* also appears in *container*.
    For different scope kinds: conservative True (assume contained).
    """
    if container.kind != test.kind:
        return True  # Conservative

    if container.kind == "file_set":
        c_items = {normalize_path(r) for r in (container.resources or [])}
        t_items = {normalize_path(r) for r in (test.resources or [])}
        return t_items.issubset(c_items)

    elif container.kind == "entity_set":
        return set(test.entities or []).issubset(set(container.entities or []))

    elif container.kind == "task_set":
        return set(test.task_ids or []).issubset(set(container.task_ids or []))

    return True  # Unknown kind: conservative
