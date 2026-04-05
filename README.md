# MPAC — Multi-Principal Agent Coordination Protocol

**When multiple AI agents — serving different people — need to work together, who coordinates them?**

MPAC is an application-layer protocol that provides coordination semantics for AI agents serving **multiple independent principals**. It handles the gap that MCP (tool invocation) and A2A (single-principal delegation) don't cover: structured coordination across organizational and trust boundaries.

**Current version: v0.1.12** — draft protocol. Conformance closure: all 21 message types have JSON Schema definitions, envelope dispatches payload by message_type, and conditional constraints are machine-enforceable.

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

The root spec, JSON Schema, and both reference implementations are fully aligned at v0.1.12. All 21 message types now have dedicated payload schemas with `if/then` conditional constraints, and the envelope schema dispatches payload validation by `message_type`. The Python reference implementation is the most heavily exercised path today (75 tests plus a live Claude API demo), and the TypeScript source has been updated to the same protocol shape (56 tests).

| Dimension | Covered | Remaining gaps |
|-----------|---------|----------------|
| Message types | **21 of 21** including `OP_BATCH_COMMIT` and `INTENT_CLAIM_STATUS` | — |
| State machines | Full lifecycle: Expiry Cascade, Auto-Dismiss, FROZEN/SUSPENDED, resume/unfreeze, SUPERSEDED, TRANSFERRED | Frozen-scope progressive degradation |
| Liveness | Heartbeat tracking, unavailability detection, intent suspension, proposal abandonment, reconnection restoration, claim withdrawal on owner return | Role-based liveness policy enforcement |
| Governance | ACK → ESCALATE → phase-scoped RESOLUTION, duplicate-resolution rejection, claim approval attribution | Frozen scope enforcement |
| Intent lifecycle | Announce, Update (objective/scope/TTL), Withdraw, Claim, `INTENT_CLAIM_STATUS`, `TRANSFERRED` alignment | Richer scope narrowing validation on claims |
| Security | Credential exchange (5 types), sender incarnation tracking, snapshot anti-replay checkpoint persistence | Signature verification, runtime replay rejection, trust binding |
| Session lifecycle | `SESSION_INFO` execution model declaration, SESSION_CLOSE, auto-close, summary, post-close rejection | Transcript export policy persistence |
| Consistency & execution model | Post-commit and governance-only pre-commit authorization/completion flow, coordinator epoch on outbound messages | Multi-coordinator fencing during live handover |
| Fault recovery | Coordinator status/heartbeat, v0.1.12 snapshot format, snapshot recovery + audit log replay, coordinator epoch bump on recovery | Split-brain detection, multi-coordinator election |
| Robustness | OP_SUPERSEDE chains, batch commit tracking, claim conflict / resolution conflict handling | Conformance harness in a Node-enabled TypeScript CI lane |

---

## What's Next

**P1 — Verification and hardening:**
- TypeScript build/test execution in a Node-enabled environment and refreshed `dist/` artifacts
- runtime replay rejection and Lamport monotonicity enforcement across reconnect / restart
- split-brain fencing and live handover validation for `coordinator_epoch`
- frozen-scope progressive degradation implementation
- Additional test coverage for v0.1.12 normative additions (scope expansion re-evaluation edge cases, batch pre-commit disambiguation, GOODBYE transfer path)

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
