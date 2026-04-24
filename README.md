# mpac-mcp

[![arXiv](https://img.shields.io/badge/arXiv-2604.09744-b31b1b.svg)](https://arxiv.org/abs/2604.09744)
[![PyPI](https://img.shields.io/pypi/v/mpac-mcp.svg)](https://pypi.org/project/mpac-mcp/)

📄 **Paper:** [MPAC: A Multi-Principal Agent Coordination Protocol for Interoperable Multi-Agent Collaboration](https://arxiv.org/abs/2604.09744) (arXiv:2604.09744)

`mpac-mcp` is the MCP-facing bridge for MPAC — it lets MCP-aware coding
clients (Claude Code, Cursor, any MCP host) participate in an MPAC
coordination session without re-implementing the protocol themselves.
The underlying protocol and reference runtime live in
[`mpac-protocol`](https://github.com/KaiyangQ/mpac-protocol) / the
[`mpac`](https://pypi.org/project/mpac/) package.

It does not re-implement the coordination protocol. Instead it:

- detects the current repository context
- ensures a local MPAC sidecar is running
- queries the sidecar for shared coordination state
- exposes high-level tools to MCP-compatible coding clients

All bundled smoke scripts now run against an isolated scratch workspace copied
from the requested repo path, so repeated runs do not inherit stale conflicts
or frozen scope from a long-lived sidecar session.

## What's in the box

**MCP tools** exposed to Claude Code / Cursor / any MCP host:

- `who_is_working`, `begin_task`, `check_overlap`, `get_file_state`
- `ack_conflict`, `submit_change`, `yield_task`
- `escalate_conflict`, `resolve_conflict`, `take_over_task`

**Two operating modes:**

1. **Local sidecar** (default). `mpac-mcp` auto-starts an in-process MPAC
   coordinator on a workspace-derived `127.0.0.1` port. Two editors on the same
   machine see each other's intents and conflicts with zero setup.
2. **Remote coordinator** (`mpac-mcp-relay`). Connect your local `claude -p`
   to a hosted MPAC coordinator over WebSocket; participate in a shared
   multi-agent session from your own laptop. See `src/mpac_mcp/relay.py` +
   `src/mpac_mcp/relay_tools.py`.

**Bundled smoke scripts** exercise specific flows against a scratch workspace
(runs are isolated — no leftover intents between runs):

- `milestone0` — two processes, one local coordinator
- `smoke_tools` — `begin_task` → `check_overlap`
- `smoke_commit` — `begin_task` → `submit_change` → `yield_task`
- `smoke_governance` — `ack_conflict` → `escalate_conflict` → `resolve_conflict`
- `smoke_takeover` — GOODBYE with transfer → `take_over_task`
- `smoke_remote` — drive the bridge against a hosted coordinator via `ws://…`

## Multi-tenant Hosted Mode (Authenticated Profile)

When deploying a hosted coordinator for multiple projects/teams:

1. Set `MPAC_TOKEN_TABLE` as a JSON env var mapping bearer tokens to allowed sessions:
   ```json
   {
     "<token-for-alice>": {"allowed_sessions": ["proj-alpha"], "roles": ["contributor"]},
     "<token-for-bob>":   {"allowed_sessions": ["proj-beta"],  "roles": ["contributor"]}
   }
   ```

2. Start the sidecar in multi-session mode:
   ```bash
   mpac-mcp-sidecar --multi-session --host 0.0.0.0 --port 8766 --tls
   ```
   The sidecar auto-detects `MPAC_TOKEN_TABLE` and switches to `security_profile=authenticated`.

3. Clients connect with their token in the HELLO credential field:
   ```
   wss://your-host/session/proj-alpha
   ```
   Tokens bound to `proj-alpha` can only join `proj-alpha` — cross-session access returns `CREDENTIAL_REJECTED`.

## Design

`mpac-mcp` is intentionally thin: MPAC itself remains the runtime and
coordination engine (see the [`mpac`](https://pypi.org/project/mpac/) package
and the [`mpac-protocol`](https://github.com/KaiyangQ/mpac-protocol) spec);
`mpac-mcp` is the MCP integration layer that translates protocol messages
into tool calls an LLM-driven editor can invoke.

## Running the Milestone 0 smoke check

From this repository root:

```bash
python3 src/mpac_mcp/milestone0.py --workspace .
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
python3 src/mpac_mcp/smoke_tools.py --workspace .
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
python3 src/mpac_mcp/smoke_commit.py --workspace .
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
python3 src/mpac_mcp/smoke_governance.py --workspace .
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
python3 src/mpac_mcp/smoke_takeover.py --workspace .
```

This will:

- ensure the local sidecar is running
- launch one client that leaves with `GOODBYE(intent_disposition="transfer")`
- verify the sidecar exposes a suspended intent
- call `take_over_task(...)`
- verify the replacement intent becomes active
