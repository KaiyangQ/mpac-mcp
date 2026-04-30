# MPAC — Multi-Principal Agent Coordination Protocol

[![arXiv](https://img.shields.io/badge/arXiv-2604.09744-b31b1b.svg)](https://arxiv.org/abs/2604.09744)

📄 **Paper:** [MPAC: A Multi-Principal Agent Coordination Protocol for Interoperable Multi-Agent Collaboration](https://arxiv.org/abs/2604.09744) (arXiv:2604.09744)

> **External users:** this is the active development branch. For the curated public release — protocol spec, reference implementations, pip package, and a worked two-machine collaboration example — see the [`opensource` branch](https://github.com/KaiyangQ/Agent_talking/tree/opensource) or check out tag [`v0.1.13`](https://github.com/KaiyangQ/Agent_talking/releases/tag/v0.1.13).

**When multiple AI agents — serving different people — need to work together, who coordinates them?**

MPAC is an application-layer protocol that provides coordination semantics for AI agents serving **multiple independent principals**. It handles the gap that MCP (tool invocation) and A2A (single-principal delegation) don't cover: structured coordination across organizational and trust boundaries.

**Current version: v0.1.15** — draft protocol. Conformance closure: all 21 message types have JSON Schema definitions, envelope dispatches payload by message_type, and conditional constraints are machine-enforceable. v0.1.14 added the optional `INTENT_DEFERRED` message for non-claiming "yield" signals; v0.1.15 tightens `INTENT_ANNOUNCE` arrival semantics with a cross-principal scope race lock (`STALE_INTENT` error code) — same-resource collisions are now hard-rejected at announce time instead of producing advisory `CONFLICT_REPORT`s, mirroring source-control's split between merge conflicts (must resolve) and semantic conflicts (warn, defer to CI).

→ [Read the introduction](./blog/introducing-mpac.md) for a full overview of the problem, design, and demo walkthrough.

---

## Core Concept

MPAC organizes multi-agent coordination into five layers:

| Layer | Purpose |
|-------|---------|
| **Session** | Agents join, discover each other, negotiate capabilities |
| **Intent** | Agents declare what they *plan* to do before doing it |
| **Operation** | Agents propose and commit changes to shared state |
| **Conflict** | Overlapping scopes or contradictory goals are detected and surfaced as structured objects |
| **Governance** | Conflicts are resolved through arbitration, escalation, or policy — with human override always available |

The protocol defines 21 message types, 3 state machines with normative transition tables (Intent, Operation, Conflict), Lamport clock watermarking for causal ordering, explicit consistency and execution models, atomic batch operations, and three security/compliance profiles.

---

## Repository Structure

```
SPEC.md                          ← Protocol specification (source of truth)
MPAC_Developer_Reference.md      ← Developer reference: data dictionary, state machines, enums
MPAC_v0.1.3_Audit_Report.md      ← Five-dimension audit report (informed v0.1.4 revision)
blog/
  introducing-mpac.md            ← Introduction article for external audience
ref-impl/
  schema/                        ← JSON Schema (wire format definitions, Draft 2020-12)
    envelope.schema.json         ← oneOf dispatcher: validates payload per message_type
    messages/                    ← 21 message payload schemas (complete coverage)
    objects/                     ← 4 shared object schemas (Watermark, Scope, Basis, Outcome)
  python/                        ← Python reference implementation
    mpac/                        ← 8 core modules
    tests/                       ← 12 test files (122 test cases)
  typescript/                    ← TypeScript reference implementation
    src/                         ← 8 source files
    tests/                       ← 11 test files (101 test cases)
  demo/
    README.md                    ← Demo guide: purpose, protocol coverage, and architecture
mpac-package/                    ← Pip-installable package (pip install ./mpac-package)
mpac-starter-kit.zip             ← Self-contained kit to send to collaborators
tests/                           ← E2E and multi-scenario test scripts
  test_e2e.py                    ← Basic two-agent E2E test
  test_e2e_scenarios.py          ← 6-scenario E2E test (long-lived connections, mutual yield)
  test_interactive.py            ← Interactive agent flow test
  test_ultimate.py               ← 5-scenario ultimate test (pre-commit, claim, escalation, task_set)
examples/
  two_machine_demo/
    host/                        ← Host site: coordinator + workspace + Agent Alice
    guest/                       ← Join site: Agent Bob connects to remote coordinator
    run_interop.sh               ← Cross-language interoperability test
    run_ai_agents.py             ← AI agent demo (2 Claude agents coordinating via MPAC)
    ai_demo_transcript.json      ← Full protocol transcript from the AI demo
    distributed/                 ← Distributed validations (WebSocket + live multi-agent scenarios)
      ws_coordinator.py          ← WebSocket coordinator server
      ws_agent.py                ← WebSocket AI agent client
      run_distributed.py         ← Network-based distributed demo
      run_e2e.py                 ← End-to-end test: real code fixes + optimistic concurrency
      trip_agent.py              ← Consumer-planning agent with per-principal preferences
      run_family_trip.py         ← Family trip validation: 3 agents plan a shared itinerary
      run_precommit_claim.py     ← Pre-commit + INTENT_CLAIM: fault recovery demo
      run_escalation.py          ← Conflict escalation to arbiter demo
      family_trip_transcript.json ← Full transcript from the family-trip run
      test_project/src/          ← 5 Python files with intentional bugs for agents to fix
version_history/                 ← Protocol evolution: archived versions, changelogs, reviews
daily_reports/                   ← Development logs
```

---

## Quick Start

### Read the Spec

The full protocol specification lives in [SPEC.md](./SPEC.md) — 30 sections covering all five layers, security profiles, compliance profiles, coordinator fault tolerance, session lifecycle, consistency model, execution model, and cross-lifecycle state machine rules with normative transition tables.

For implementation, the [Developer Reference](./MPAC_Developer_Reference.md) provides a complete data dictionary: 10 core objects, 21 message types in the current spec lineage, 3 state machines, 8 enum registries, and an implementation checklist. (Note: the Developer Reference may lag behind the spec by one version; `SPEC.md` is always the source of truth.)

### Run the Reference Implementations

**Python:**
```bash
cd ref-impl/python
pip install -e .
pytest tests/
```

**TypeScript:**
```bash
cd ref-impl/typescript
npm install && npm run build
npm test
```

### Cross-Language Interoperability Test

Verifies that Python and TypeScript implementations produce identical wire formats:
```bash
cd ref-impl/demo
bash run_interop.sh
```

This exchanges 14 messages bidirectionally between the two implementations with zero wire format deviation.

### AI Agent Demo

Two Claude agents (Alice: security engineer, Bob: code quality engineer) independently decide what to work on in a shared codebase, announce intents through MPAC, negotiate when the coordinator detects a scope overlap conflict, and exercise v0.1.5+ features (coordinator status, state snapshot, session close):

```bash
# Requires Anthropic API key in local_config.json
cd ref-impl/demo
python run_ai_agents.py
```

The full transcript from a successful run is available at [ai_demo_transcript.json](./ref-impl/demo/ai_demo_transcript.json).

### Distributed Validations

MPAC has 7 live AI agent demos that exercise all 21 protocol message types across multiple domains. See the [Demo README](./ref-impl/demo/README.md) for a complete guide including protocol coverage, architecture, and message type mapping.

**Code-editing end-to-end validation**

The real-world validation suite tests MPAC over WebSocket transport with concurrent Claude agents that actually modify code files. Two agents independently read a test project with intentional security bugs, generate fixes via Claude API, and commit changes through the full MPAC lifecycle — including conflict detection, coordinator auto-resolution, and optimistic concurrency control with rebase on stale commits:

```bash
# Requires: pip install websockets httpx anthropic
cd ref-impl/demo/distributed
python run_e2e.py
```

This demonstrates:
- **WebSocket transport binding** — MPAC messages serialized, transmitted, and deserialized over real network connections
- **Concurrent LLM decision-making** — parallel Claude API calls for intent decisions, conflict positions, and code generation
- **Real file coordination** — agents read, fix, and commit actual Python source files with SHA-256 state_ref tracking
- **Optimistic concurrency control** — stale commits rejected with `STALE_STATE_REF`; agents rebase on the latest committed version and retry

See the [Distributed Validation Report](./version_history/v0.1.12_conformance_closure/MPAC_v0.1.12_Distributed_Validation.md) for detailed findings and architecture.

**Family Trip multi-principal validation**

The second distributed scenario validates MPAC outside software engineering. Three agents serving Dad, Mom, and Kid plan a 5-day family vacation, negotiate overlapping claims on itinerary days and budget categories, and commit a shared itinerary through the same WebSocket coordinator:

```bash
# Requires: pip install websockets httpx anthropic
cd ref-impl/demo/distributed
python run_family_trip.py
```

This demonstrates:
- **Multi-principal consumer coordination** — independent agents serve different family members with distinct goals and authority
- **`task_set` scope overlap detection** — itinerary days and budget categories are coordinated as shared resources
- **Natural-language conflict negotiation** — agents express structured positions and compromises through `CONFLICT_ACK`
- **Atomic planning commits** — itinerary updates are committed via `OP_BATCH_COMMIT` with `all_or_nothing` semantics

See the [Family Trip Use Case](./version_history/v0.1.12_conformance_closure/MPAC_v0.1.12_Family_Trip_Use_Case.md) and [Family Trip Validation Report](./version_history/v0.1.12_conformance_closure/MPAC_v0.1.12_Family_Trip_Validation.md) for the scenario design and actual run results.

**Coordination Overhead vs Decision Time**

The third distributed scenario provides empirical evidence for MPAC's core academic claim: **MPAC eliminates coordination overhead without compressing decision time.** The same 3-agent cross-module PR review runs in both Traditional (serial) and MPAC (protocol-coordinated) modes, with precise per-segment timing:

```bash
# Requires: pip install websockets httpx anthropic
cd ref-impl/demo/distributed
python run_overhead_comparison.py
```

This demonstrates:
- **Decision time preservation** — same Claude prompts in both modes produce comparable decision times (~60s total)
- **Coordination overhead elimination** — serialization waits, round-trip clarifications, and post-hoc conflict rework drop by **95%** under MPAC
- **Pre-emptive conflict detection** — `INTENT_ANNOUNCE` scope overlap catches conflicts before work begins, vs. traditional post-hoc discovery
- **Parallel execution** — all three agents review, submit conflict positions, and commit in parallel via WebSocket

**Pre-Commit + INTENT_CLAIM Fault Recovery**

The fourth distributed scenario exercises the pre-commit execution model and agent fault recovery. Three agents work in governance mode: one agent's proposal is authorized then committed, another's is rejected after intent withdrawal, and when the third agent crashes, its work is claimed by a surviving agent via `INTENT_CLAIM`:

```bash
cd ref-impl/demo/distributed
python run_precommit_claim.py
```

This demonstrates:
- **Pre-commit authorization flow** — `OP_PROPOSE` → `COORDINATOR_STATUS(authorization)` → `OP_COMMIT` completion
- **INTENT_UPDATE** — agent expands scope mid-session, triggering new conflict detection
- **INTENT_WITHDRAW + OP_REJECT** — agent withdraws intent; subsequent proposal rejected with `intent_terminated`
- **Agent crash recovery** — liveness timeout detects unavailable agent, suspends intents, surviving agent claims via `INTENT_CLAIM` with governance approval

**Conflict Escalation to Arbiter**

The fifth distributed scenario demonstrates multi-level governance. Two owner agents dispute a scope overlap, escalate to a designated arbiter, and the arbiter renders a binding decision via Claude:

```bash
cd ref-impl/demo/distributed
python run_escalation.py
```

This demonstrates:
- **CONFLICT_ACK with dispute** — both agents acknowledge the conflict as "disputed"
- **CONFLICT_ESCALATE** — agent escalates unresolved conflict to a designated arbiter
- **Arbiter resolution** — arbiter analyzes both positions via Claude and issues a binding `RESOLUTION`
- **Multi-level governance** — owner → arbiter authority chain with Claude-powered judicial decision-making

---

## Remote Collaboration (pip package)

MPAC is available as a pip-installable Python package. Two people on different computers can run AI agents that collaboratively edit shared code files through the protocol.

**Host (starts coordinator + workspace):**
```bash
cd examples/two_machine_demo/host
pip install ../../../mpac-package
python run.py
# Shows: ws://your-ip:8766 — share this with collaborator
```

**Collaborator (joins remotely):**
```bash
pip install mpac_protocol-0.1.0-py3-none-any.whl
python run.py ws://host-ip:8766
```

Or send `mpac-starter-kit.zip` to the collaborator — it contains the `.whl`, `run.py`, and a README with setup instructions.

Both users get an interactive CLI where they can view workspace files, give tasks to their agent, and see color-coded diffs of changes. Real-time notifications show when the other agent commits changes. The coordinator holds all files in memory; agents read/write through WebSocket — no shared filesystem needed.

For cross-network collaboration (different WiFi), use [ngrok](https://ngrok.com): `ngrok http 8766` creates a public URL.

### MPACAgent API

The pip package exposes the full MPAC protocol through `MPACAgent`:

| Method | Protocol Feature |
|--------|-----------------|
| `execute_task(task)` | Full autonomous workflow: intent → conflict check → fix → commit |
| `do_propose(intent_id, op_id, target)` | Pre-commit authorization (OP_PROPOSE → COORDINATOR_STATUS) |
| `propose_and_commit(...)` | Complete pre-commit flow (propose → auth → commit) |
| `do_claim_intent(...)` | Fault recovery: take over a crashed agent's suspended intent |
| `do_escalate_conflict(...)` | Escalate a dispute to a designated arbiter |
| `do_resolve_conflict(...)` | Arbiter renders a binding resolution |
| `do_ack_conflict(...)` | Acknowledge or dispute a conflict |

Agents support custom `roles` (owner, arbiter, contributor) and content-agnostic operation (code, documents, config files, or any text).

### Automated Tests (pip package)

Two test suites validate the pip package end-to-end with live Claude API calls:

**6-scenario E2E test** — two agents with long-lived connections:
```bash
source examples/two_machine_demo/host/.venv/bin/activate
python tests/test_e2e_scenarios.py
```
Covers: no-conflict, conflict detection, dependency chains, conflict + rebase, asymmetric yield, and mutual yield auto-retry.

**5-scenario ultimate test** — multi-agent, multi-scope-type, multi-execution-model:
```bash
source examples/two_machine_demo/host/.venv/bin/activate
python tests/test_ultimate.py
```

| Scenario | Scope | Execution Model | Key Features |
|----------|-------|-----------------|-------------|
| Code collaboration | file_set | post_commit | Conflict + rebase |
| Family trip planning | task_set | post_commit | 3-agent conflict + resolution |
| Document co-editing | file_set | post_commit | Agent generalization (.md files) |
| Pre-commit governance | file_set | pre_commit | OP_PROPOSE + INTENT_CLAIM fault recovery |
| Conflict escalation | file_set | governance | CONFLICT_ESCALATE + arbiter RESOLUTION |

---

## API Key Configuration

The AI agent and distributed validation demos require an Anthropic API key. Copy the example config and add your key:

```bash
cp local_config.example.json local_config.json
```

```json
{
  "anthropic": {
    "api_key": "your_key_here",
    "model": "claude-sonnet-4-6"
  }
}
```

Do not commit `local_config.json` to a public repository.

---

## Current Coverage

The root spec and the Python reference implementation are aligned at v0.1.15. The TypeScript reference implementation is currently at v0.1.13 — the v0.1.14 (`INTENT_DEFERRED`) and v0.1.15 (race lock + fast-resolve clarification) additions are TODO there. All 21 message types have dedicated payload schemas with `if/then` conditional constraints, and the envelope schema dispatches payload validation by `message_type`. Both implementations enforce 6 runtime rules (HELLO-first gate, credential validation, resolution authority, frozen-scope blocking, batch atomicity rollback, complete error codes). The Python implementation has 97 mpac tests + 49 mpac-mcp tests (including v0.1.15's 9 race-lock + fast-resolve invariant tests) plus live Claude API demos. Distributed validations verify the protocol over WebSocket transport across five domains: code editing with optimistic concurrency control, family trip planning with `task_set`-based negotiation, coordination overhead measurement, pre-commit authorization with fault recovery, and conflict escalation to arbiter. All 21 message types have live Claude API demo coverage.

| Dimension | Covered | Remaining gaps |
|-----------|---------|----------------|
| Message types | **21 of 21** including `OP_BATCH_COMMIT` and `INTENT_CLAIM_STATUS` | — |
| State machines | Full lifecycle: Expiry Cascade, Auto-Dismiss, FROZEN/SUSPENDED, resume/unfreeze, SUPERSEDED, TRANSFERRED | Frozen-scope progressive degradation |
| Liveness | Heartbeat tracking, unavailability detection, intent suspension, proposal abandonment, reconnection restoration, claim withdrawal on owner return | Role-based liveness policy enforcement |
| Governance | ACK → ESCALATE → phase-scoped RESOLUTION, duplicate-resolution rejection, claim approval attribution, **resolution authority enforcement** (owner/arbiter pre-escalation, escalate_to/arbiter post-escalation) | — |
| Intent lifecycle | Announce, Update (objective/scope/TTL), Withdraw, Claim, `INTENT_CLAIM_STATUS`, `TRANSFERRED` alignment, **v0.1.15 cross-principal scope race lock** (announce-time hard reject for same-resource collisions with `STALE_INTENT`, same-principal exemption preserved), **v0.1.14 INTENT_DEFERRED** (non-claiming yield signal with three-axis cleanup + arrival-time fast-resolve) | Richer scope narrowing validation on claims; reactive event subscription so relays can forward inbound `CONFLICT_REPORT` / `INTENT_WITHDRAW` into running LLM subprocesses (closes the "first to announce sees nothing" gap) |
| Security | Credential exchange (5 types), **credential validation on HELLO** (authenticated/verified profiles), **HELLO-first gate**, **role policy evaluation** (Section 23.1.5, no-policy rejection), **replay protection** (duplicate message_id + timestamp window rejection), sender incarnation tracking, snapshot anti-replay checkpoint persistence | Signature verification, trust binding |
| Session lifecycle | `SESSION_INFO` execution model declaration, SESSION_CLOSE (spec-aligned schema + detailed summary per Section 9.6.2), auto-close, post-close rejection | Transcript export policy persistence |
| Consistency & execution model | Post-commit and governance-only pre-commit authorization/completion flow, coordinator epoch on outbound messages, **optimistic concurrency control** (state_ref_before validation, STALE_STATE_REF rejection, rebase pattern) | Multi-coordinator fencing during live handover |
| Transport & concurrency | **WebSocket transport binding** (JSON-over-WebSocket, message-type routing), **concurrent Claude agent coordination** (parallel LLM calls) across code-editing, family-trip, overhead-comparison, pre-commit, and escalation demos, **real file modification** with SHA-256 state_ref tracking, `task_set` itinerary/budget coordination, coordinator auto-resolve for pure-agent scenarios | Additional transport bindings (gRPC, HTTP/2), multi-node coordinator |
| Fault recovery | **Backend Health Monitoring** (coordinator status/heartbeat, v0.1.13 snapshot format, snapshot recovery + audit log replay, coordinator epoch bump on recovery, automated failure detection), **INTENT_CLAIM fault recovery demo** (agent crash → liveness timeout → intent suspension → claim with governance approval) | Split-brain detection, multi-coordinator election |
| Demo coverage | **21/21 message types** with live Claude API demos across 7 distributed scenarios: code editing, family trip, overhead comparison, pre-commit authorization, agent crash recovery (INTENT_CLAIM), conflict escalation (CONFLICT_ESCALATE), and arbiter resolution | — |
| Robustness | OP_SUPERSEDE chains, batch commit tracking, **batch atomicity rollback** (all_or_nothing cleanup), **frozen-scope enforcement**, claim conflict / resolution conflict handling, **CAUSAL_GAP / INTENT_BACKOFF / STALE_INTENT error codes** | Conformance harness in a Node-enabled TypeScript CI lane; TypeScript port of v0.1.14 + v0.1.15 additions |

---

## What's Next

**P1 — Verification and hardening:**
- TypeScript build/test execution in a Node-enabled environment and refreshed `dist/` artifacts
- runtime replay rejection and Lamport monotonicity enforcement across reconnect / restart
- split-brain fencing and live handover validation for `coordinator_epoch`
- frozen-scope progressive degradation implementation
- Additional test coverage for v0.1.13 normative additions (Backend Health Monitoring alerting, extended heartbeat policies, graceful degradation under partial coordinator failure)

**P2 — Protocol evolution and verification:**
- v0.2.0 protocol advancement (scope expressiveness, post-commit rollback, cross-session coordination, compact envelope, scope-based subscription)
- Conformance test suite (automated compliance testing via JSON Schema + interop messages)
- TLA+ formal verification of state machine interactions (especially cross-lifecycle with normative transition tables)
- Performance benchmarks (scope overlap detection at scale)

---

## Contributing

MPAC is an open protocol in active development. If you're working on multi-agent systems, agent coordination frameworks, or collaborative AI applications, we'd welcome your perspective.

- **Read the spec:** [SPEC.md](./SPEC.md)
- **Try the implementations:** [Python](./ref-impl/python/) | [TypeScript](./ref-impl/typescript/)
- **Run the demos:** [Demo Guide](./ref-impl/demo/README.md) — 7 live AI agent demos covering all 21 message types
- **Review protocol evolution:** [version_history/CHANGELOG.md](./version_history/CHANGELOG.md)

---

## License

This project is in early development. License terms will be formalized as the protocol matures.
