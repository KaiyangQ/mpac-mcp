# mpac-mcp API Reference

`mpac-mcp` is an MCP server that lets coding agents (Claude Code, Cursor, any MCP client) coordinate work on the same repository through the MPAC protocol. It exposes ten tools backed by a local sidecar process that holds shared coordination state.

- **Package**: `mpac-mcp` (depends on `mpac>=0.1.0`, `mcp>=1.0.0`, `websockets>=12.0`)
- **Python**: 3.10+
- **MCP server name**: `mpac-coding`
- **Transport**: stdio (FastMCP)

## Architecture

```
┌─────────────────┐   MCP/stdio    ┌──────────────────────┐   WebSocket    ┌──────────────┐
│   MCP client    │ ─────────────> │  mpac-mcp server     │ ─────────────> │ MPAC sidecar │
│ (Claude Code,   │                │  (FastMCP, 10 tools) │                │ (shared      │
│  Cursor, …)     │ <───────────── │   coordinator_bridge │ <───────────── │  workspace)  │
└─────────────────┘                └──────────────────────┘                └──────────────┘
```

- One sidecar per workspace, auto-started on first tool call.
- Sidecar port is derived deterministically from the workspace path, so two processes in the same repo share state without any configuration.
- Each MCP server process has one persistent `Participant` session (principal id + roles) — the bridge owns whatever intents it announces, and will refuse `yield_task` / `submit_change` on intents it does not own.

## Installation

```bash
pip install mpac-mcp
```

This pulls `mpac` (the protocol core, import name `mpac_protocol`), `mcp`, and `websockets`.

## Launching the server

### Console scripts (from `pyproject.toml`)

| Script | Purpose |
| --- | --- |
| `mpac-mcp` | Start the MCP server (stdio). Register this with your MCP client. |
| `mpac-mcp-sidecar` | Start the local sidecar standalone (usually auto-started by the bridge). |
| `mpac-mcp-milestone0` | Two-process shared-state smoke check. |
| `mpac-mcp-smoke-tools` | `begin_task` + `check_overlap` end-to-end smoke. |
| `mpac-mcp-smoke-commit` | `begin → submit_change → yield` smoke. |
| `mpac-mcp-smoke-governance` | `ack → escalate → resolve` smoke. |
| `mpac-mcp-smoke-takeover` | Suspend → claim → take-over smoke. |
| `mpac-mcp-claude-setup` | Helper that prints a `.mcp.json` snippet for Claude Code. |

### Claude Code / Cursor config

```json
{
  "mcpServers": {
    "mpac-coding": {
      "type": "stdio",
      "command": "mpac-mcp",
      "env": {
        "MPAC_WORKSPACE_DIR": "/absolute/path/to/your/repo"
      }
    }
  }
}
```

## Environment variables

All variables are optional — sensible defaults are derived from the repo path.

| Variable | Default | Effect |
| --- | --- | --- |
| `MPAC_WORKSPACE_DIR` | detected via nearest `.git` ancestor | Overrides the workspace root; this is the only env var you normally need to set. |
| `MPAC_SIDECAR_HOST` | `127.0.0.1` | Sidecar bind host. |
| `MPAC_SIDECAR_PORT` | derived from workspace path (`38000–39999`) | Force a specific sidecar port. |
| `MPAC_PRINCIPAL_ID` | `agent:mpac-mcp:<pid>` | Stable principal id for this bridge session. Set it to get readable attribution across runs. |
| `MPAC_AGENT_NAME` | `mpac-mcp-<pid>` | Human-readable display name. |
| `MPAC_AGENT_ROLES` | `contributor` | Comma-separated roles (`contributor`, `arbiter`, …). Only participants with the `arbiter` role and `is_available=True` can be auto-picked by `escalate_conflict`. |
| `MPAC_AGENT_CAPABILITIES` | `intent.broadcast, intent.withdraw, intent.claim, op.commit, conflict.ack, conflict.escalate, conflict.resolve` | Comma-separated capabilities declared in the MPAC `HELLO`. |
| `MPAC_COORDINATOR_URL` | _(unset)_ | Switches the bridge into **remote mode**: connect to a hosted coordinator at this `ws://` / `wss://` URL instead of auto-starting a local sidecar. Accepts shapes `wss://host/session/<id>` (session id parsed from path) or plain `wss://host`. |
| `MPAC_SESSION_ID` | _(unset)_ | In remote mode: pin the session id explicitly. Overrides any session id embedded in `MPAC_COORDINATOR_URL`. Ignored in local mode. |
| `MPAC_COORDINATOR_TOKEN` | _(unset)_ | In remote mode: bearer token sent as `Authorization: Bearer <token>` on every WebSocket connection. Validation is expected to be performed by the reverse proxy fronting the coordinator. |

## Remote coordinator mode

By default `mpac-mcp` runs a local sidecar per workspace and keeps all coordination on `127.0.0.1`. For cross-machine collaboration — two people on different laptops editing the same shared repository — point the bridge at a **hosted MPAC coordinator** instead.

### Client-side (one env var)

```bash
export MPAC_COORDINATOR_URL="wss://mpac.example.com/session/room-alpha"
export MPAC_COORDINATOR_TOKEN="..."   # optional, reverse-proxy checks it
mpac-mcp                               # MCP server now speaks to the hosted coordinator
```

When `MPAC_COORDINATOR_URL` is set:

- `ensure_sidecar()` never spawns a local process. It only probes the remote URL and raises `SidecarError` if it is unreachable.
- Every WebSocket connection carries `Authorization: Bearer <MPAC_COORDINATOR_TOKEN>` when the token is set.
- The session id is taken from the URL path (`/session/<id>`), or from `MPAC_SESSION_ID`, or finally derived from the workspace path. When the session id is not pinned by the user, the bridge accepts whatever session id the coordinator returns.
- `BridgeConfig.is_remote` is `True` and `BridgeConfig.uri` returns `uri_override`.

### Hosting the coordinator

The same `mpac-mcp-sidecar` console script that auto-starts locally can be used as a hosted coordinator — just bind to a public interface and pass a stable session id:

```bash
mpac-mcp-sidecar \
  --host 0.0.0.0 \
  --port 8766 \
  --session-id room-alpha \
  --workspace /srv/mpac-rooms/room-alpha
```

The script prints a hosted-mode banner on startup so operators can sanity-check the bind address and the client URL.

### Auth via reverse proxy (recommended)

`mpac-mcp` client sends the bearer token, but **does not validate it**. Put a TLS-terminating reverse proxy in front of the coordinator and check the header there. Minimal Caddy example:

```caddy
mpac.example.com {
    reverse_proxy /session/* 127.0.0.1:8766 {
        header_up Authorization {http.request.header.Authorization}
    }

    @unauthed {
        not header Authorization "Bearer your-long-random-token"
    }
    respond @unauthed 401
}
```

This keeps the `mpac` core package auth-free and lets you rotate tokens, add rate limits, and log access using standard proxy features.

### Verifying the link

Run the bundled remote smoke against your hosted coordinator (it spawns a 127.0.0.1 sidecar locally and drives the bridge through a `ws://...` URL — no network involved, just the remote-mode code path):

```bash
mpac-mcp-smoke-remote --workspace .
```

Expected output shows `is_remote: True`, `begin_task: status=ok`, and the client URL printed next to the scratch workspace.

## Tools

Every tool accepts an optional `repo_path: str | None` argument. When omitted, the server falls back to `MPAC_WORKSPACE_DIR`, and then to the nearest `.git` ancestor of the server's working directory. Every successful response includes `workspace_dir` and `session_id` so clients can distinguish multi-repo sessions.

Status field values are consistent across tools:

| Status | Meaning |
| --- | --- |
| `ok` | Request accepted. |
| `success` | `submit_change` commit accepted. |
| `stale` | `submit_change` rejected — `state_ref_before` does not match current state. |
| `conflict` | `submit_change` rejected — scope frozen by an open conflict. |
| `missing` | `get_file_state` — file not found in shared workspace. |
| `error` | Protocol-level error or invalid operation (e.g. yielding an intent this bridge does not own). |
| `timeout` | `take_over_task` did not receive an `INTENT_CLAIM_STATUS` in time. |

### `who_is_working`

Return the live coordination view for the workspace.

```python
who_is_working(repo_path: str | None = None) -> dict
```

**Returns**

```jsonc
{
  "workspace_dir": "/abs/path",
  "sidecar_uri": "ws://127.0.0.1:39794",
  "session_id": "mpac-local-<slug>-<hash>",
  "participant_count": 2,
  "active_intent_count": 2,
  "open_conflict_count": 1,
  "participants":   [ /* {principal_id, display_name, roles, is_available, …} */ ],
  "active_intents": [ /* {intent_id, principal_id, objective, scope, …} */ ],
  "open_conflicts": [ /* {conflict_id, intent_a, intent_b, files, …} */ ]
}
```

### `begin_task`

Announce a file-scoped intent owned by this bridge session.

```python
begin_task(objective: str, files: list[str], repo_path: str | None = None) -> dict
```

**Behaviour** — sends `ANNOUNCE_INTENT` over the bridge's persistent participant session, drains protocol messages for ~0.6s, then returns the resulting state.

**Returns**

```jsonc
{
  "status": "ok" | "error",
  "intent_id": "intent-<name>-<rand>",
  "principal_id": "agent:...",
  "objective": "Refactor auth",
  "files": ["src/auth.py", "src/session.py"],
  "has_conflict": false,
  "conflicts": [],                 // CONFLICT_REPORT payloads involving this intent
  "errors":    [],                 // PROTOCOL_ERROR payloads (populated when status == "error")
  "intent":    { /* full intent record from sidecar */ },
  "workspace_dir": "...",
  "session_id":    "..."
}
```

### `check_overlap`

Return foreign intents (not owned by this bridge) whose scope overlaps a proposed file set. Does not announce anything.

```python
check_overlap(files: list[str], repo_path: str | None = None) -> dict
```

**Returns**

```jsonc
{
  "workspace_dir": "...",
  "session_id":    "...",
  "proposed_files": ["src/auth.py"],
  "has_overlap": true,
  "overlaps": [
    {
      "intent_id":    "intent-alice-…",
      "principal_id": "agent:alice",
      "objective":    "Add MFA",
      "scope": {"kind": "file_set", "resources": ["src/auth.py"]}
    }
  ]
}
```

### `get_file_state`

Read a single file from the shared sidecar workspace with its current `state_ref`. Use the returned `state_ref` as `state_ref_before` when calling `submit_change`.

```python
get_file_state(
    path: str,
    repo_path: str | None = None,
    include_content: bool = True,
) -> dict
```

**Returns**

```jsonc
{
  "status": "ok" | "missing",
  "path":   "src/auth.py",
  "state_ref": "sha256:…",          // only when status == "ok"
  "size":   1024,                    // only when status == "ok"
  "content": "def login(): …",       // when include_content=True and status == "ok"
  "workspace_dir": "...",
  "session_id":    "..."
}
```

### `submit_change`

Attempt one `OP_COMMIT` against a single file the bridge already owns an intent for. On success the sidecar writes the new content and updates its `state_ref`.

```python
submit_change(
    intent_id: str,
    target: str,
    content: str,
    state_ref_before: str,
    repo_path: str | None = None,
) -> dict
```

**Returns**

```jsonc
{
  "status": "success" | "stale" | "conflict" | "error",
  "intent_id": "intent-…",
  "target":    "src/auth.py",
  "state_ref_after":   "sha256:…",    // only on success
  "current_state_ref": "sha256:…",    // sidecar's current view (useful on stale)
  "conflicting_files": ["src/auth.py"], // empty on success
  "message": "Commit accepted",
  "workspace_dir": "...",
  "session_id":    "..."
}
```

**Errors**

- `stale` — `state_ref_before` doesn't match; re-read via `get_file_state` and retry.
- `conflict` — scope frozen by an open conflict; resolve first (see `ack_conflict` / `resolve_conflict`).
- `error` — other protocol errors, or the intent is not owned by this bridge process.

### `yield_task`

Withdraw an owned intent via `INTENT_WITHDRAW`.

```python
yield_task(
    intent_id: str,
    reason: str = "yielded",
    repo_path: str | None = None,
) -> dict
```

Fails with `status == "error"` if the intent was not announced by this bridge process.

### `ack_conflict`

Acknowledge or dispute an open conflict.

```python
ack_conflict(
    conflict_id: str,
    ack_type: str = "seen",       // or "dispute"
    repo_path: str | None = None,
) -> dict
```

Returns `status: "ok"` plus the refreshed `open_conflicts` list.

### `escalate_conflict`

Escalate a conflict to an arbiter. If `escalate_to` is omitted, the bridge picks the unique available participant with role `arbiter`; if there isn't exactly one, it returns `status: "error"` and asks you to pass `escalate_to` explicitly.

```python
escalate_conflict(
    conflict_id: str,
    reason: str,
    repo_path: str | None = None,
    escalate_to: str | None = None,     // arbiter principal_id
    context:     str | None = None,
) -> dict
```

### `resolve_conflict`

Resolve a conflict as owner or arbiter.

```python
resolve_conflict(
    conflict_id: str,
    decision: str,                       // e.g. "accept_a", "merge", "drop"
    repo_path: str | None = None,
    rationale: str | None = None,
    outcome:  dict | None = None,        // arbitrary structured outcome
) -> dict
```

**Returns** — `{status, conflict_id, decision, remaining_conflict, open_conflicts, message}`. `remaining_conflict` is non-null if the sidecar still lists this conflict as open after the resolution.

### `take_over_task`

Claim a suspended intent and create a replacement intent owned by this bridge. Used for "Alice went offline mid-task, Bob takes over." Waits synchronously for `INTENT_CLAIM_STATUS`.

```python
take_over_task(
    original_intent_id: str,
    repo_path: str | None = None,
    new_objective: str | None = None,           // default: inherit original
    files: list[str] | None = None,             // default: inherit scope.resources
    original_principal_id: str | None = None,   // default: inferred from sidecar summary
    justification: str | None = None,
) -> dict
```

**Returns**

```jsonc
{
  "status": "ok" | "rejected" | "timeout" | "error",
  "decision": "approved" | "rejected" | ...,
  "claim_id":            "claim-…",
  "original_intent_id":  "intent-alice-…",
  "new_intent_id":       "intent-mpac-mcp-claim-…",
  "message": "…",
  "workspace_dir": "...",
  "session_id":    "..."
}
```

On `approved`, the new intent is recorded as owned by this bridge and can be used with `submit_change` / `yield_task`.

## Sidecar wire protocol

The sidecar also accepts two lightweight query messages used internally by the bridge — documented here for anyone building alternative clients.

### `SESSION_SUMMARY`

```jsonc
// request
{"type": "SESSION_SUMMARY"}
// response
{"type": "SESSION_SUMMARY_RESPONSE", "session": { /* session snapshot */ }}
```

Fields on `session`: `session_id`, `participant_count`, `active_intent_count`, `open_conflict_count`, `participants`, `active_intents`, `open_conflicts`.

### `FILE_READ`

```jsonc
// request
{"type": "FILE_READ", "path": "src/auth.py"}
// response (found)
{"type": "FILE_CONTENT", "path": "src/auth.py", "state_ref": "sha256:…", "content": "…"}
// response (missing)
{"type": "FILE_ERROR", "path": "src/auth.py", "error": "…"}
```

Full MPAC protocol messages (`HELLO`, `ANNOUNCE_INTENT`, `OP_COMMIT`, `CONFLICT_REPORT`, `INTENT_CLAIM`, `INTENT_CLAIM_STATUS`, …) go through the participant WebSocket session established by the bridge and are defined in the `mpac` (`mpac_protocol`) package.

## Python-level helpers

`mpac_mcp.coordinator_bridge` exports async helper functions with the same names as the MCP tools (`who_is_working`, `begin_task`, `check_overlap`, `get_file_state`, `ack_conflict`, `yield_task`, `submit_change`, `escalate_conflict`, `take_over_task`, `resolve_conflict`) plus infrastructure hooks:

- `ensure_sidecar(start=None) -> BridgeConfig` — idempotently start the local sidecar for a workspace.
- `launch_ephemeral_sidecar(start=None) -> (BridgeConfig, Popen)` — for tests; refuses to start if one is already running.
- `stop_sidecar(process)` — terminate an ephemeral sidecar.
- `fetch_session_summary(config)` / `fetch_file_state(config, path)` — raw sidecar queries.
- `LocalParticipantBridge` — persistent `Participant` session per `(workspace, principal_id, roles)` key, cached in `_BRIDGES`.
- `who_is_working_sync(start=None)` — synchronous wrapper for non-async hosts.

`mpac_mcp.config` exports `BridgeConfig`, `detect_workspace_dir`, `derive_session_id`, `derive_sidecar_port`, `build_bridge_config`.

## Smoke scripts

All smoke scripts run against an isolated scratch workspace copied from the requested repo path, so repeated runs do not inherit stale conflicts or frozen scope:

```bash
mpac-mcp-milestone0    --workspace .    # two processes share one sidecar
mpac-mcp-smoke-tools   --workspace .    # begin_task + check_overlap
mpac-mcp-smoke-commit  --workspace .    # begin -> submit_change -> yield
mpac-mcp-smoke-governance --workspace . # ack -> escalate -> resolve
mpac-mcp-smoke-takeover   --workspace . # suspend -> claim -> take over
```

Each script prints a compact summary of the final session state (participants, active intents, open conflicts).
