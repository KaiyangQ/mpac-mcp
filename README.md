# MPAC — Multi-Principal Agent Coordination Protocol

**When multiple AI agents — serving different people — need to work together, who coordinates them?**

MPAC is an application-layer protocol that provides coordination semantics for AI agents serving **multiple independent principals**. It handles the gap that MCP (tool invocation) and A2A (single-principal delegation) don't cover: structured coordination across organizational and trust boundaries.

**Current version: v0.1.10** — draft protocol. The root spec is ahead of the reference implementations; implementation coverage currently trails the newest closure fixes.

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
    envelope.schema.json
    messages/                    ← 11 message payload schemas
    objects/                     ← 4 shared object schemas (Watermark, Scope, Basis, Outcome)
  python/                        ← Python reference implementation
    mpac/                        ← 8 core modules
    tests/                       ← 9 test files (70 test cases)
  typescript/                    ← TypeScript reference implementation
    src/                         ← 8 source files
    tests/                       ← 9 test files (56 test cases)
  demo/
    run_interop.sh               ← Cross-language interoperability test
    run_ai_agents.py             ← AI agent demo (2 Claude agents coordinating via MPAC)
    ai_demo_transcript.json      ← Full protocol transcript from the AI demo
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

---

## API Key Configuration

The AI agent demo requires an Anthropic API key. Copy the example config and add your key:

```bash
cp local_config.example.json local_config.json
```

```json
{
  "anthropic": {
    "api_key": "your_key_here",
    "model": "claude-sonnet-4-20250514"
  }
}
```

Do not commit `local_config.json` to a public repository.

---

## Current Coverage

The reference implementations cover most of the v0.1.8 protocol surface across both Python and TypeScript (70 + 56 tests, 14-message cross-language interop, real Claude API end-to-end verification), but they do not yet fully cover the newest v0.1.9-v0.1.10 closure changes:

| Dimension | Covered | Not yet covered |
|-----------|---------|-----------------|
| Message types | **19 of 21** (90%) | `OP_BATCH_COMMIT`, `INTENT_CLAIM_STATUS` |
| State machines | Full lifecycle: Expiry Cascade, Auto-Dismiss, FROZEN/SUSPENDED, resume/unfreeze, SUPERSEDED | — |
| Liveness | Heartbeat tracking, unavailability detection, intent suspension, proposal abandonment, reconnection restoration | — |
| Governance | ACK → ESCALATE → Arbiter RESOLUTION, auto-escalation on resolution timeout | Frozen scope enforcement |
| Intent lifecycle | Announce, Update (objective/scope/TTL), Withdraw, Claim (first-claim-wins) | — |
| Security | Credential exchange (5 types), enum definitions | Signature verification, replay detection, role-based access |
| Session lifecycle | SESSION_CLOSE, auto-close, summary, post-close rejection | Transcript export, lifecycle policy persistence |
| Consistency & execution model | — | Pre-commit confirmation flow, execution_model in SESSION_INFO (new in v0.1.7) |
| Fault recovery | Coordinator status/heartbeat, state snapshot, snapshot recovery + audit log replay | Split-brain detection, multi-coordinator election |
| Coordinator accountability | — | Coordinator message signing, tamper-evident coordinator log (new in v0.1.7, Verified profile) |
| Frozen scope | — | Progressive degradation 3-phase system (new in v0.1.7) |
| Robustness | Liveness detection, INTENT_CLAIM, disconnection recovery, OP_SUPERSEDE chains | — |

---

## What's Next

**P1 — v0.1.10 conformance closure:**
- `OP_BATCH_COMMIT` handler (atomic multi-target operations)
- `INTENT_CLAIM_STATUS` handler and `TRANSFERRED` intent-state alignment
- `coordinator_epoch` fencing in coordinator recovery / handover flows
- `sender_instance_id` support and Lamport monotonicity tests across reconnect / restart
- anti-replay checkpoint persistence across snapshot recovery
- pre-commit authorization / completion flow and governance-only `pre_commit` enforcement
- escalated-conflict authority gating and arbiter-finality handling
- claim approval attribution (`approved_by`) and `TRANSFERRED`-aware conflict auto-dismiss
- JSON Schema synchronization with the v0.1.10 envelope and payload requirements
- `MPAC_Developer_Reference.md` synchronization with the v0.1.10 root spec

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
- **Run the AI demo:** [ref-impl/demo/run_ai_agents.py](./ref-impl/demo/run_ai_agents.py)
- **Review protocol evolution:** [version_history/CHANGELOG.md](./version_history/CHANGELOG.md)

---

## License

This project is in early development. License terms will be formalized as the protocol matures.
