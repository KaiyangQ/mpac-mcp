# MPAC v0.1.13 Update Record — Backend Health Monitoring

**Date:** 2026-04-07
**Previous version:** v0.1.12
**Scope:** New feature — backend AI model health monitoring integrated with aistatus.cc, enabling agents to declare backend dependencies, report provider health in heartbeats, and trigger coordinator-mediated alerts and model switching governance.

---

## Motivation

MPAC v0.1.12 provides robust agent-level liveness detection through `HEARTBEAT` messages and `unavailability_timeout_sec`. However, these mechanisms only detect whether the **agent process** is alive — not whether the **AI model backend** the agent depends on (e.g., Claude API, GPT-4 API) is operational. An agent process can remain alive and sending heartbeats while its underlying LLM provider is experiencing a major outage, resulting in a "zombie agent" that occupies intent scope but cannot make progress.

The open-source [aistatus.cc](https://aistatus.cc) project provides free, public JSON APIs for real-time AI provider status monitoring, including a `/api/check` endpoint designed specifically for agent pre-flight checks with automatic fallback suggestions. This version integrates aistatus.cc's data model into MPAC, enabling:

1. Agents to **declare** their backend model dependency at session join time
2. Agents to **report** backend health alongside their own heartbeat status
3. Coordinators to **broadcast alerts** when a participant's backend degrades or goes down
4. Sessions to **govern model switching** through configurable policy (allowed/notify_first/forbidden)
5. Other agents to **claim intents** from agents whose backends are down, using the existing `INTENT_CLAIM` mechanism

---

## Changes

### New Feature — Backend Health Monitoring

#### HELLO Payload Extension

Added optional `backend` field to the `HELLO` payload, allowing agents to declare their AI model dependency at session join time:

| Field | Type | Req | Description |
|-------|------|-----|-------------|
| `backend` | object | O | Agent's AI model backend dependency |
| `backend.model_id` | string | R (within backend) | Full model identifier in `provider/model` format (e.g., `anthropic/claude-sonnet-4.6`) |
| `backend.provider` | string | R (within backend) | Provider slug (e.g., `anthropic`, `openai`, `google`) |

The `provider` and `model_id` format aligns with the aistatus.cc API convention, enabling direct use with `GET /api/check?model={model_id}`.

#### HEARTBEAT Payload Extension

Added optional `backend_health` field to the `HEARTBEAT` payload:

| Field | Type | Req | Description |
|-------|------|-----|-------------|
| `backend_health` | object | O | Backend provider health status |
| `backend_health.model_id` | string | R (within backend_health) | Current model identifier |
| `backend_health.provider_status` | string | R (within backend_health) | One of: `operational`, `degraded`, `down`, `unknown` |
| `backend_health.status_detail` | string | O | Human-readable status detail (e.g., "Elevated error rates") |
| `backend_health.checked_at` | string (date-time) | R (within backend_health) | ISO 8601 timestamp of the last health check |
| `backend_health.alternatives` | array | O | Alternative providers/models when current is degraded/down |
| `backend_health.switched_from` | string | O | Previous model_id if the agent has switched backends |
| `backend_health.switch_reason` | string | O | Reason for switch. One of: `provider_down`, `provider_degraded`, `manual`, `cost_optimization` |

The `provider_status` enum and `alternatives` structure directly mirror the aistatus.cc `/api/check` response format.

#### COORDINATOR_STATUS Extension

Added `backend_alert` to the `event` enum, with conditional fields:

| Field | Type | Req | Description |
|-------|------|-----|-------------|
| `affected_principal` | string | C | Required when `event` = `backend_alert`: principal ID of the affected agent |
| `backend_detail` | object | C | Required when `event` = `backend_alert`: backend health details |
| `backend_detail.model_id` | string | R (within backend_detail) | Affected model identifier |
| `backend_detail.provider_status` | string | R (within backend_detail) | One of: `operational`, `degraded`, `down`, `unknown` |
| `backend_detail.status_detail` | string | O | Human-readable status detail |
| `backend_detail.alternatives` | array | O | Alternative providers/models |

#### Liveness Policy Extension

Added optional `backend_health_policy` to the `liveness_policy` in `SESSION_INFO`:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `backend_health_policy` | object | absent | Backend health monitoring configuration |
| `backend_health_policy.enabled` | boolean | `false` | Whether backend health monitoring is active |
| `backend_health_policy.check_source` | string | `"https://aistatus.cc/api/check"` | URL of the status check API |
| `backend_health_policy.check_interval_sec` | number | `60` | How often agents should check backend health |
| `backend_health_policy.on_degraded` | string | `"warn"` | Action when provider is degraded. One of: `ignore`, `warn`, `suspend_and_claim` |
| `backend_health_policy.on_down` | string | `"suspend_and_claim"` | Action when provider is down. One of: `ignore`, `warn`, `suspend_and_claim` |
| `backend_health_policy.auto_switch` | string | `"allowed"` | Model switching governance. One of: `allowed`, `notify_first`, `forbidden` |
| `backend_health_policy.allowed_providers` | string[] | absent (no restriction) | Whitelist of providers the agent may switch to. Configured by the session creator (principal/user), not by the protocol. |

**Protocol vs. implementation boundary:** The protocol defines the signaling mechanism (backend declaration, health reporting, alert broadcasting, switch governance) and the coordinator's enforcement rules (whitelist check, auto_switch policy). The protocol does NOT prescribe which alternative model to choose, when to trigger a switch, or whether to switch back after recovery — these are implementation-level decisions made by each agent.

---

### Version Bump

All version strings updated to `0.1.13` across:
- `SPEC.md` (title, body, examples)
- `envelope.schema.json` (description)
- Python: `coordinator.py`, `envelope.py`, `__init__.py`, `pyproject.toml`
- TypeScript: `coordinator.ts`, `envelope.ts`, `package.json`

---

## Impact on Reference Implementations

Both reference implementations require additions:

1. **`_handle_hello` / `handleHello`**: Store `backend` from HELLO payload in `ParticipantInfo`
2. **`_handle_heartbeat` / `handleHeartbeat`**: Read `backend_health` from HEARTBEAT payload, evaluate `provider_status` against `backend_health_policy`, emit `COORDINATOR_STATUS(event=backend_alert)` when thresholds are crossed, validate `auto_switch` and `allowed_providers` when `switched_from` is present
3. **`ParticipantInfo`**: New fields `backend_model_id`, `backend_provider`, `backend_provider_status`
4. **`CoordinatorEvent` enum**: New value `BACKEND_ALERT`

All changes are additive — no existing behavior is modified.

---

## Test Results

- Python: 109/109 tests passed (all existing tests pass with zero regressions)
- TypeScript: 88/88 tests passed (all existing tests pass with zero regressions)
