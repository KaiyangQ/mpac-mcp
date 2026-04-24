#!/usr/bin/env bash
# sync-opensource-branches.sh — sync `opensource` + `opensource-mcp`
# branches to current `main`, then push to private Agent_talking + the
# two public repos (mpac-protocol, mpac-mcp).
#
# The two public repos are the external-facing face of MPAC:
#   github.com/KaiyangQ/mpac-protocol  ← tracks local `opensource` branch
#   github.com/KaiyangQ/mpac-mcp       ← tracks local `opensource-mcp` branch
#
# `opensource` keeps the same layout as main (mpac-package/ at path
# mpac-package/). `opensource-mcp` PROMOTES main's mpac-mcp/* to repo
# root — its layout is that of a standalone package repo.
#
# Unlike sync-deploy-branch.sh (orphan commits, force-push), this script
# ADDS commits on top of each branch so the git history is preserved for
# public contributors. Each run produces one sync commit per branch.
#
# Each run:
#   1. Verifies required remotes are configured.
#   2. Tags current public-repo tips as opensource-archive-YYYY-MM-DD
#      and opensource-mcp-archive-YYYY-MM-DD (idempotent).
#   3. Updates local `opensource` with main's content for whitelisted paths.
#   4. Updates local `opensource-mcp` with main's mpac-mcp/* at root.
#   5. Pushes both branches + archive tags to origin + public remotes.
#
# READMEs are NOT auto-synced — the two public repos have curated READMEs
# that describe them as standalone projects, and main's READMEs have
# monorepo-relative paths. If a README goes stale after a feature change,
# edit the opensource branch directly.
#
# Run from repo root, on `main`, with no uncommitted changes.
set -euo pipefail

# Paths copied from main to the `opensource` branch. README.md is NOT in
# this list — see comment above.
OPENSOURCE_PATHS=(
    mpac-package
    blog
    examples
    ref-impl
    version_history
    MPAC_Developer_Reference.md
    SPEC.md
    LICENSE
    .gitignore
    local_config.example.json
    mpac-starter-kit.zip
)

# ── preconditions ───────────────────────────────────────────────────────

if [[ "$(git branch --show-current)" != "main" ]]; then
    echo "error: must run from the main branch (currently $(git branch --show-current))" >&2
    exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "error: working tree has uncommitted changes to tracked files" >&2
    git status --short >&2
    exit 1
fi

for remote in origin mpac-protocol mpac-mcp-public; do
    if ! git remote get-url "$remote" >/dev/null 2>&1; then
        cat >&2 <<EOF
error: required remote '$remote' is not configured.

  git remote add mpac-protocol   https://github.com/KaiyangQ/mpac-protocol.git
  git remote add mpac-mcp-public https://github.com/KaiyangQ/mpac-mcp.git
EOF
        exit 1
    fi
done

today=$(date +%Y-%m-%d)

echo "=== fetching public state ==="
git fetch origin --quiet
git fetch mpac-protocol --quiet
git fetch mpac-mcp-public --quiet

# ── archive tags (idempotent) ────────────────────────────────────────────

echo "=== archiving current public state as opensource*-archive-$today ==="
for pair in \
    "opensource-archive-$today:mpac-protocol/main" \
    "opensource-mcp-archive-$today:mpac-mcp-public/main"; do
    tag="${pair%%:*}"
    ref="${pair##*:}"
    if git rev-parse --verify --quiet "refs/tags/$tag" >/dev/null; then
        echo "  skip: tag $tag already exists"
    else
        git tag "$tag" "$ref"
        echo "  tag: $tag -> $ref"
    fi
done

# ── sync opensource ────────────────────────────────────────────────────

echo "=== syncing opensource branch ==="
worktree_os=$(mktemp -d)/opensource-sync
git worktree add --quiet "$worktree_os" opensource

(
    cd "$worktree_os"
    # Remove old copies so any files dropped from main also get dropped here.
    for p in "${OPENSOURCE_PATHS[@]}"; do
        git rm -rf --quiet --ignore-unmatch -- "$p" 2>/dev/null || true
    done
    # Repopulate from main.
    git checkout main -- "${OPENSOURCE_PATHS[@]}"
    git add -A
    if git diff --cached --quiet; then
        echo "  no changes — opensource already up to date"
    else
        git commit --quiet -m "Sync opensource to main @ $today"
        echo "  committed: $(git rev-parse --short HEAD)"
    fi
)

git worktree remove --force "$worktree_os"

# ── sync opensource-mcp ─────────────────────────────────────────────────

echo "=== syncing opensource-mcp branch ==="
worktree_mcp=$(mktemp -d)/opensource-mcp-sync
git worktree add --quiet "$worktree_mcp" opensource-mcp

(
    cd "$worktree_mcp"
    # Remove all tracked files so any deletions on main propagate.
    git ls-files -z | xargs -0 git rm -f --quiet
    # Extract main's mpac-mcp/ content at repo root (strip the prefix).
    git archive main mpac-mcp | tar -x --strip-components=1
    # LICENSE on main lives at repo root, not inside mpac-mcp/.
    git checkout main -- LICENSE
    # Add exactly the files from main's mpac-mcp/ + LICENSE — never `git
    # add -A` (worktrees can pick up unrelated untracked files otherwise).
    {
        git ls-tree -r main mpac-mcp/ --name-only | sed 's|^mpac-mcp/||'
        echo LICENSE
    } | xargs git add
    if git diff --cached --quiet; then
        echo "  no changes — opensource-mcp already up to date"
    else
        git commit --quiet -m "Sync opensource-mcp to main @ $today"
        echo "  committed: $(git rev-parse --short HEAD)"
    fi
)

git worktree remove --force "$worktree_mcp"

# ── push ────────────────────────────────────────────────────────────────

echo "=== pushing to origin (private) ==="
git push origin opensource opensource-mcp
git push origin "opensource-archive-$today" "opensource-mcp-archive-$today" 2>&1 \
    | grep -v "Everything up-to-date" || true

echo "=== pushing to mpac-protocol (public) ==="
git push mpac-protocol opensource:main
git push mpac-protocol "opensource-archive-$today" 2>&1 \
    | grep -v "Everything up-to-date" || true

echo "=== pushing to mpac-mcp-public (public) ==="
git push mpac-mcp-public opensource-mcp:main
git push mpac-mcp-public "opensource-mcp-archive-$today" 2>&1 \
    | grep -v "Everything up-to-date" || true

echo ""
echo "✅ Sync complete. Public repos updated to main @ $today."
echo ""
echo "Follow-up steps (manual):"
echo "  • Tag PyPI releases if you shipped one: git tag -a vX.Y.Z <branch> && git push <remote> vX.Y.Z"
echo "  • If a README is stale after new features, edit opensource/README.md"
echo "    or opensource-mcp/README.md directly — they are NOT auto-synced."
