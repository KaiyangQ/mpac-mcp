"""Reverse-import scanner for cross-file dependency-breakage detection.

Given a set of *target files* (what a participant intends to modify) and
the *project's Python source*, return the other files whose static imports
reach any symbol defined in a target. Callers then pin this set into
``Scope.extensions["impact"]`` before announcing the intent; the coordinator
reports a ``dependency_breakage`` conflict when another participant's edits
land on a file in someone else's impact set.

The scanner is source-agnostic: it operates on a ``Mapping[path, content]``
so the same code works for filesystem projects (MCP/CLI, Claude Code) and
for database-backed projects (MPAC web-app, where files live in the
``ProjectFile`` table). Two thin adapters are provided — see
:func:`scan_reverse_deps_from_dir` and :func:`collect_python_sources_from_dir`.

Design notes
------------
* **Analyzer at the announce layer, not in core coordinator detection.**
  Computed at the layer that sees the source (local FS for MCP, DB for the
  web-app), emitted as ``scope.extensions.impact`` on the announce envelope.
* **Static analysis only.** ``importlib.import_module`` / ``__import__``
  targets are invisible. Consistent with pyright/ruff; we accepted this
  tradeoff when scoping v0.2.1.
* **One level of reverse dependency.** No transitive closure. If A → B → C
  and we're editing C, we flag B. Editing C doesn't flag A. Revisit in 0.3+
  if real usage shows the one-hop rule missing too many conflicts.
* **Fail soft.** Any per-file error (syntax, encoding, I/O) is swallowed —
  a broken file in the project must never break conflict detection.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Set, Tuple


# Directories we never descend into when scanning the filesystem. Virtualenvs,
# build output, vendored deps, tool caches — parsing them wastes time and
# pollutes the impact set with noise.
_SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".hg", ".svn",
    "venv", ".venv", "env", ".env",
    "dist", "build", ".tox", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "site-packages", ".eggs",
}


_RELATIVE_IMPORT_RE = re.compile(r"^(\.+)(.*)$")


# ── Path / module conversion ────────────────────────────────────────────

def _normalize_rel(path: str) -> str:
    """Turn any path into project-root-relative POSIX form.

    Callers pass a mix of ``./foo.py``, ``foo/bar.py``, ``\\foo\\bar.py``.
    We standardize to forward slashes and strip leading ``./`` so the
    mapping lookups are reliable across OSes.
    """
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def _path_to_module(rel_path: str) -> Optional[str]:
    """Convert a project-relative .py path to a dotted module name.

    Returns None for non-python files. ``__init__.py`` collapses to the
    package name (``pkg/sub/__init__.py`` → ``pkg.sub``).
    """
    if not rel_path.endswith(".py"):
        return None
    stem = rel_path[:-3]  # strip .py
    parts = [p for p in stem.split("/") if p]
    if not parts:
        return None
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return None
    return ".".join(parts)


def _extract_imports(source: str, filename: str = "<unknown>") -> List[str]:
    """Parse ``source`` and return the module names it imports.

    Absolute imports appear verbatim (``from foo.bar import x`` → ``foo.bar``).
    Relative imports keep their leading dots (``from . import x`` → ``.``;
    ``from ..pkg import y`` → ``..pkg``) so the caller can resolve them
    against the importing file's package.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except (SyntaxError, ValueError):
        # ValueError covers null-byte-in-source on some platforms.
        return []

    modules: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            mod = node.module or ""
            modules.append("." * level + mod)
    return modules


def _resolve_relative(rel_import: str, importer_rel_path: str) -> Optional[str]:
    """Turn ``..pkg.sub`` (seen in ``importer_rel_path``) into an absolute
    dotted module name.

    Returns None if the relative path escapes the project root.
    """
    m = _RELATIVE_IMPORT_RE.match(rel_import)
    if not m or not m.group(1):
        return rel_import  # not actually relative

    dots = len(m.group(1))
    rest = m.group(2)

    # Parent directory of the importing file = its package.
    importer_parts = [p for p in importer_rel_path.split("/") if p and p != "."]
    # Drop the filename itself (last segment).
    pkg_parts = importer_parts[:-1] if importer_parts else []

    # ``from . import x`` ⇒ same package, pops 0 dirs;
    # ``from .. import x`` ⇒ pops 1 dir; etc.
    pops = dots - 1
    if pops > len(pkg_parts):
        return None
    if pops:
        pkg_parts = pkg_parts[:-pops]

    combined = list(pkg_parts)
    if rest:
        combined.extend(rest.split("."))
    return ".".join(combined) if combined else None


# ── Core scanner (source-agnostic) ──────────────────────────────────────

def scan_reverse_deps(
    target_files: Iterable[str],
    project_files: Mapping[str, str],
) -> List[str]:
    """Return the files in ``project_files`` that statically import any
    symbol defined in ``target_files``.

    Parameters
    ----------
    target_files:
        Project-relative paths of the files whose reverse dependencies we
        want. Absolute paths are not meaningful here — normalize before
        calling if needed.
    project_files:
        Mapping of project-relative path → file content. Callers supply
        whatever subset they can see; non-.py entries are silently skipped.

    Returns
    -------
    Sorted list of project-relative paths (POSIX separators) that import
    from at least one target. Target files are excluded from the result.
    """
    targets_norm: Set[str] = {_normalize_rel(t) for t in target_files}
    target_modules: Set[str] = set()
    for t in targets_norm:
        m = _path_to_module(t)
        if m:
            target_modules.add(m)
    if not target_modules:
        return []

    result: Set[str] = set()

    for raw_path, content in project_files.items():
        rel = _normalize_rel(raw_path)
        if not rel.endswith(".py"):
            continue
        if rel in targets_norm:
            continue

        for imp in _extract_imports(content, filename=rel):
            resolved = (
                _resolve_relative(imp, rel)
                if imp.startswith(".")
                else imp
            )
            if not resolved:
                continue
            # Exact match OR submodule of a target package
            # (``from target_pkg.sub import x`` when target is
            # ``target_pkg/__init__.py``).
            for tmod in target_modules:
                if resolved == tmod or resolved.startswith(tmod + "."):
                    result.add(rel)
                    break
            else:
                continue
            break  # first hit is enough; next file

    return sorted(result)


# ── Filesystem adapter ──────────────────────────────────────────────────

def collect_python_sources_from_dir(project_root: str) -> Dict[str, str]:
    """Walk ``project_root`` and return a ``{rel_path: content}`` map of
    every .py file outside the standard skip list.

    Useful as the ``project_files`` argument to :func:`scan_reverse_deps`
    for callers that have the project on local disk (MCP / CLI).
    """
    root = Path(project_root)
    if not root.is_dir():
        return {}
    root_resolved = root.resolve()

    out: Dict[str, str] = {}
    for py_file in root.rglob("*.py"):
        try:
            rel = py_file.resolve().relative_to(root_resolved)
        except (ValueError, OSError):
            continue
        if any(
            part in _SKIP_DIRS or (part.startswith(".") and part != ".")
            for part in rel.parts
        ):
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out[str(rel).replace(os.sep, "/")] = content
    return out


def scan_reverse_deps_from_dir(
    target_files: Iterable[str],
    project_root: str,
) -> List[str]:
    """Filesystem convenience wrapper around :func:`scan_reverse_deps`.

    Target paths may be absolute or relative to ``project_root``; absolute
    paths are rebased to project-relative before matching.
    """
    root = Path(project_root)
    if not root.is_dir():
        return []
    root_resolved = root.resolve()

    targets_rel: List[str] = []
    for f in target_files:
        p = Path(f)
        if p.is_absolute():
            try:
                rel = p.resolve().relative_to(root_resolved)
                targets_rel.append(str(rel).replace(os.sep, "/"))
            except (ValueError, OSError):
                continue
        else:
            targets_rel.append(_normalize_rel(f))

    sources = collect_python_sources_from_dir(project_root)
    return scan_reverse_deps(targets_rel, sources)
