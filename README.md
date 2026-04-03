# MPAC — Multi-Principal Agent Coordination Protocol

**When multiple AI agents — serving different people — need to work together, who coordinates them?**

MPAC is an application-layer protocol that provides coordination semantics for AI agents serving **multiple independent principals**. It handles the gap that MCP (tool invocation) and A2A (single-principal delegation) don't cover: structured coordination across organizational and trust boundaries.

**Current version: v0.1.4** — draft protocol with working reference implementations. Not yet a production standard.

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

The protocol defines 17 message types, 3 state machines (Intent, Operation, Conflict), Lamport clock watermarking for causal ordering, and three security/compliance profiles.

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
    messages/                    ← 8 message payload schemas
    objects/                     ← 4 shared object schemas (Watermark, Scope, Basis, Outcome)
  python/                        ← Python reference implementation
    mpac/                        ← 8 core modules
    tests/                       ← 7 test files (40 test cases)
  typescript/                    ← TypeScript reference implementation
    src/                         ← 8 source files
    tests/                       ← 7 test files (34 test cases)
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

The full protocol specification lives in [SPEC.md](./SPEC.md) — 24 sections covering all five layers, security profiles, compliance profiles, and cross-lifecycle state machine rules.

For implementation, the [Developer Reference](./MPAC_Developer_Reference.md) provides a complete data dictionary: 10 core objects, 17 message types, 3 state machines, 8 enum registries, and an implementation checklist.

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

Two Claude agents (Alice: security engineer, Bob: code quality engineer) independently decide what to work on in a shared codebase, announce intents through MPAC, and negotiate when the coordinator detects a scope overlap conflict:

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

The reference implementations cover ~85% of protocol semantics across both Python and TypeScript (40 + 34 tests, 14-message cross-language interop):

| Dimension | Covered | Not yet covered |
|-----------|---------|-----------------|
| Message types | 16 of 17 (all except OP_SUPERSEDE) | OP_SUPERSEDE handler |
| State machines | Full lifecycle: Expiry Cascade, Auto-Dismiss, FROZEN/SUSPENDED, resume/unfreeze | — |
| Liveness | Heartbeat tracking, unavailability detection, intent suspension, proposal abandonment, reconnection restoration | — |
| Governance | ACK → ESCALATE → Arbiter RESOLUTION, auto-escalation on resolution timeout | Frozen scope enforcement |
| Intent lifecycle | Announce, Update (objective/scope/TTL), Withdraw, Claim (first-claim-wins) | — |
| Security | Enum definitions | Signature verification, replay detection, role-based access |
| Robustness | Liveness detection, INTENT_CLAIM, disconnection recovery | Coordinator failover |

---

## What's Next

**P0 — Remaining gaps:**
- OP_SUPERSEDE handler (last unimplemented message type)
- Publish JSON Schema as standalone referenceable artifacts

**P1 — Security and enforcement:**
- Authenticated security profile (signing, replay detection)
- Frozen scope enforcement (block OP_COMMIT while conflict OPEN/ESCALATED)
- Multi-agent scenarios (3+ agents, governance conflicts, timeouts)

**P2 — Conformance and verification:**
- Conformance test suite (automated compliance testing via JSON Schema + interop messages)
- TLA+ formal verification of state machine interactions
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
