"""Scope overlap detection for MPAC."""
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
