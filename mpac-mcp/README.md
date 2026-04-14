# mpac-mcp

`mpac-mcp` is the MCP-facing bridge for MPAC.

It does not re-implement the coordination protocol. Instead it:

- detects the current repository context
- ensures a local MPAC sidecar is running
- queries the sidecar for shared coordination state
- exposes high-level tools to MCP-compatible coding clients

All bundled smoke scripts now run against an isolated scratch workspace copied
from the requested repo path, so repeated runs do not inherit stale conflicts
or frozen scope from a long-lived sidecar session.

## Current scope

This initial scaffold focuses on the shortest end-to-end path:

- local sidecar auto-discovery / auto-start
- repository-root detection
- session summary query
- first MCP tools:
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
- a Milestone 0 validation script for "two processes share one local coordinator"
- an end-to-end smoke script for "one external client + one MCP-owned task"
- an end-to-end smoke script for "begin task -> submit change -> yield task"
- an end-to-end smoke script for "ack -> escalate -> resolve"
- an end-to-end smoke script for "suspend -> claim -> take over"

## Development status

This directory is the start of the `mpac-mcp` product entry point. It is
intentionally thin: MPAC remains the runtime and coordination engine;
`mpac-mcp` is the integration layer.

## Running the Milestone 0 smoke check

From this repository root:

```bash
python3 mpac-mcp/src/mpac_mcp/milestone0.py --workspace .
```

This will:

- derive a deterministic local sidecar port from the repo path
- start the local sidecar if it is not already running
- launch two independent demo clients
- announce two overlapping intents
- query the sidecar summary and print the result

## Running the tool smoke check

From this repository root:

```bash
python3 mpac-mcp/src/mpac_mcp/smoke_tools.py --workspace .
```

This will:

- ensure the local sidecar is running
- launch one independent demo client
- call `begin_task(...)` through the bridge
- call `check_overlap(...)`
- confirm that overlap is visible through shared sidecar state

## Running the commit smoke check

From this repository root:

```bash
python3 mpac-mcp/src/mpac_mcp/smoke_commit.py --workspace .
```

This will:

- ensure the local sidecar is running
- call `begin_task(...)`
- call `submit_change(...)` once with a derived `state_ref_before`
- verify the sidecar state changed
- call `yield_task(...)`

## Running the governance smoke check

From this repository root:

```bash
python3 mpac-mcp/src/mpac_mcp/smoke_governance.py --workspace .
```

This will:

- ensure the local sidecar is running
- launch one contributor client and one arbiter client
- call `begin_task(...)` to create a real overlap
- call `ack_conflict(...)`
- call `escalate_conflict(...)`
- call `resolve_conflict(...)`

## Running the takeover smoke check

From this repository root:

```bash
python3 mpac-mcp/src/mpac_mcp/smoke_takeover.py --workspace .
```

This will:

- ensure the local sidecar is running
- launch one client that leaves with `GOODBYE(intent_disposition="transfer")`
- verify the sidecar exposes a suspended intent
- call `take_over_task(...)`
- verify the replacement intent becomes active
