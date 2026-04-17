# Claude Code Setup For `mpac-mcp`

This guide connects the current repository to Claude Code using a local
`stdio` MCP server.

## Why local scope first

For the current development stage, the recommended path is **local scope**
rather than a shared project `.mcp.json`:

- the server path is still repo-local
- the setup is per-developer and easiest to debug
- it avoids committing machine-specific absolute paths

This follows Claude Code's documented MCP flow for local `stdio` servers:
[Claude Code MCP docs](https://code.claude.com/docs/en/mcp)

## Prerequisites

- `python3`
- Claude Code installed and `claude` available on your `PATH`
- the Python `mcp` package available in the environment used to launch the server

If `mpac-mcp` isn't installed as a package yet, the setup below still works
because it injects `PYTHONPATH` pointing at the local source trees.

## Generate the exact command for this repo

From the repository root:

```bash
python3 mpac-mcp/src/mpac_mcp/claude_setup.py --scope local
```

That prints a ready-to-run command like:

```bash
claude mcp add --transport stdio --scope local --env PYTHONPATH=/abs/repo/mpac-mcp/src:/abs/repo/mpac-package/src --env MPAC_WORKSPACE_DIR=/abs/repo mpac-coding -- python3 /abs/repo/mpac-mcp/src/mpac_mcp/server.py
```

Run that command once to register the server with Claude Code.

## Verify the server is connected

1. Start Claude Code in this repository
2. Run `/mcp`
3. Confirm `mpac-coding` appears in the server list

## Current tools

The current `mpac-mcp` server exposes:

- `who_is_working`
- `begin_task`
- `check_overlap`
- `get_file_state`
- `ack_conflict`
- `submit_change`
- `yield_task`
- `escalate_conflict`
- `resolve_conflict`
- `take_over_task`

## Recommended first prompt

After connecting the server, a good first prompt is:

> Use the mpac-coding tools to inspect who is working in this repo, then announce a task to update `README.md`, check for overlap, read the shared file state, and tell me what tool results you got.

## Minimal intended workflow

The current expected Claude Code flow is:

1. `who_is_working`
2. `begin_task`
3. `check_overlap`
4. `get_file_state`
5. edit content locally in Claude Code
6. `submit_change`
7. `yield_task` when done or when yielding

Advanced governance / recovery flow:

1. `ack_conflict`
2. `escalate_conflict`
3. `resolve_conflict`
4. `take_over_task` when the original owner left suspended work

## Generate a `.mcp.json` payload if needed

If you want to inspect a project-scoped JSON config payload:

```bash
python3 mpac-mcp/src/mpac_mcp/claude_setup.py --format json
```

This prints a valid `.mcp.json` object for the current repository, but for now
the recommended path is still the local-scope `claude mcp add ...` command.
