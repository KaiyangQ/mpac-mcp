"""MCP server entry point for mpac-mcp."""

from __future__ import annotations

from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from coordinator_bridge import ack_conflict as ack_conflict_bridge
    from coordinator_bridge import begin_task as begin_task_bridge
    from coordinator_bridge import check_overlap as check_overlap_bridge
    from coordinator_bridge import escalate_conflict as escalate_conflict_bridge
    from coordinator_bridge import get_file_state as get_file_state_bridge
    from coordinator_bridge import resolve_conflict as resolve_conflict_bridge
    from coordinator_bridge import submit_change as submit_change_bridge
    from coordinator_bridge import take_over_task as take_over_task_bridge
    from coordinator_bridge import who_is_working as who_is_working_bridge
    from coordinator_bridge import yield_task as yield_task_bridge
else:
    from .coordinator_bridge import ack_conflict as ack_conflict_bridge
    from .coordinator_bridge import begin_task as begin_task_bridge
    from .coordinator_bridge import check_overlap as check_overlap_bridge
    from .coordinator_bridge import escalate_conflict as escalate_conflict_bridge
    from .coordinator_bridge import get_file_state as get_file_state_bridge
    from .coordinator_bridge import resolve_conflict as resolve_conflict_bridge
    from .coordinator_bridge import submit_change as submit_change_bridge
    from .coordinator_bridge import take_over_task as take_over_task_bridge
    from .coordinator_bridge import who_is_working as who_is_working_bridge
    from .coordinator_bridge import yield_task as yield_task_bridge

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - depends on optional runtime install
    FastMCP = None


if FastMCP is not None:
    mcp = FastMCP("mpac-coding")

    @mcp.tool()
    async def who_is_working(repo_path: str | None = None) -> dict:
        """Return the active MPAC coordination state for the current repo."""
        return await who_is_working_bridge(repo_path)

    @mcp.tool()
    async def begin_task(
        objective: str,
        files: list[str],
        repo_path: str | None = None,
    ) -> dict:
        """Announce a task and return the resulting MPAC coordination state."""
        return await begin_task_bridge(objective, files, repo_path)

    @mcp.tool()
    async def check_overlap(
        files: list[str],
        repo_path: str | None = None,
    ) -> dict:
        """Check whether a proposed file set overlaps active intents."""
        return await check_overlap_bridge(files, repo_path)

    @mcp.tool()
    async def get_file_state(
        path: str,
        repo_path: str | None = None,
        include_content: bool = True,
    ) -> dict:
        """Return the shared workspace state_ref and optional content for one file."""
        return await get_file_state_bridge(path, repo_path, include_content=include_content)

    @mcp.tool()
    async def ack_conflict(
        conflict_id: str,
        ack_type: str = "seen",
        repo_path: str | None = None,
    ) -> dict:
        """Acknowledge or dispute a conflict."""
        return await ack_conflict_bridge(conflict_id, ack_type, repo_path)

    @mcp.tool()
    async def yield_task(
        intent_id: str,
        reason: str = "yielded",
        repo_path: str | None = None,
    ) -> dict:
        """Withdraw a previously announced task owned by this MCP bridge."""
        return await yield_task_bridge(intent_id, reason, repo_path)

    @mcp.tool()
    async def submit_change(
        intent_id: str,
        target: str,
        content: str,
        state_ref_before: str,
        repo_path: str | None = None,
        ) -> dict:
        """Attempt a single commit and return success/stale/conflict/error."""
        return await submit_change_bridge(
            intent_id,
            target,
            content,
            state_ref_before,
            repo_path,
        )

    @mcp.tool()
    async def escalate_conflict(
        conflict_id: str,
        reason: str,
        repo_path: str | None = None,
        escalate_to: str | None = None,
        context: str | None = None,
    ) -> dict:
        """Escalate a conflict to a specific or inferred arbiter."""
        return await escalate_conflict_bridge(
            conflict_id,
            reason,
            repo_path,
            escalate_to=escalate_to,
            context=context,
        )

    @mcp.tool()
    async def take_over_task(
        original_intent_id: str,
        repo_path: str | None = None,
        new_objective: str | None = None,
        files: list[str] | None = None,
        original_principal_id: str | None = None,
        justification: str | None = None,
    ) -> dict:
        """Claim a suspended intent and create a replacement task."""
        return await take_over_task_bridge(
            original_intent_id,
            repo_path,
            new_objective=new_objective,
            files=files,
            original_principal_id=original_principal_id,
            justification=justification,
        )

    @mcp.tool()
    async def resolve_conflict(
        conflict_id: str,
        decision: str,
        repo_path: str | None = None,
        rationale: str | None = None,
        outcome: dict | None = None,
    ) -> dict:
        """Resolve a conflict as an owner or arbiter."""
        return await resolve_conflict_bridge(
            conflict_id,
            decision,
            repo_path,
            rationale=rationale,
            outcome=outcome,
        )


def main() -> int:
    if FastMCP is None:
        print(
            "The 'mcp' package is not installed. Install dependencies for "
            "mpac-mcp before running the MCP server.",
            file=sys.stderr,
        )
        return 1

    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
