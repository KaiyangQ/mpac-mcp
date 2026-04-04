# Introducing MPAC: A Coordination Protocol for Multi-Agent Collaboration

*When multiple AI agents — serving different people — need to work together, who coordinates them?*

## The Problem

The AI agent ecosystem is growing fast. MCP lets agents discover and use tools. A2A lets one orchestrator delegate tasks to other agents. But both assume a **single controlling principal** — one person or organization that owns and trusts all the agents involved.

What happens when that assumption breaks?

Consider a software team where Alice's coding agent and Bob's coding agent are both working on the same codebase. Alice's agent wants to refactor the authentication module. Bob's agent wants to fix a performance bug in the same files. Neither agent reports to the other. Neither principal (Alice or Bob) has authority over the other's agent. Yet their agents are about to create a merge conflict — or worse, silently overwrite each other's work.

This isn't a hypothetical. As AI agents become more autonomous, multi-principal coordination is becoming a real, unsolved infrastructure problem. It shows up whenever:

- Two people's agents touch the same shared resources
- Agents from different teams or organizations need to collaborate
- Multiple stakeholders have competing priorities over shared state
- Someone needs to audit *who decided what and why* across organizational boundaries

MCP doesn't address this — it's about tool invocation, not inter-principal coordination. A2A doesn't either — it explicitly assumes a single orchestrator with full authority. The coordination layer between independent principals and their agents is simply missing.

## What MPAC Does

MPAC (Multi-Principal Agent Coordination Protocol) fills this gap. It's an application-layer protocol that provides coordination semantics for agents serving **multiple independent principals**.

The core idea is simple: important actions should be declared before executed, conflicts should be made explicit rather than hidden, and decisions should carry enough context to be auditable.

MPAC organizes this into five layers:

| Layer | What it does |
|-------|-------------|
| **Session** | Agents join, discover each other, negotiate capabilities |
| **Intent** | Agents announce what they *plan* to do before doing it |
| **Operation** | Agents propose and commit actual changes to shared state |
| **Conflict** | Overlapping scopes or contradictory goals are detected and reported as structured objects |
| **Governance** | Conflicts are resolved through arbitration, escalation, or policy — with human override always available |

This layering is what makes MPAC different from "just use a message queue" or "just add locking." It separates *planning* from *execution* from *dispute* from *governance*, so each concern can be handled independently without tangling them into application logic.

## How It Works in Practice

Here's what a real MPAC session looks like, using two AI agents (Claude) that independently decide what to work on:

**Setup:** A Flask web application has several known issues — a token expiry bug, N+1 queries, code duplication. Two AI agents join a session: Alice (security engineer) and Bob (code quality engineer).

**Phase 1 — Session Join:**
```
Alice  → Coordinator:  HELLO  (roles: contributor, capabilities: intent.broadcast, op.commit)
Coordinator → Alice:   SESSION_INFO  (profile: open, compliance: core)
Bob    → Coordinator:  HELLO
Coordinator → Bob:     SESSION_INFO
```

**Phase 2 — Intent Declaration:**

Each agent independently calls Claude to decide what to work on. Alice decides to fix token expiry validation in `auth.py` and `auth_middleware.py`. Bob decides to refactor auth logic to eliminate duplication — in `auth.py`, `auth_middleware.py`, and `models.py`.

```
Alice → Coordinator:  INTENT_ANNOUNCE
  intent_id: "intent-alice-token-expiry-fix"
  scope: { kind: "file_set", resources: ["src/auth.py", "src/auth_middleware.py"] }

Bob   → Coordinator:  INTENT_ANNOUNCE
  intent_id: "intent-bob-refactor-auth-models"
  scope: { kind: "file_set", resources: ["src/auth.py", "src/auth_middleware.py", "src/models.py"] }
```

**Phase 3 — Automatic Conflict Detection:**

The coordinator detects that both intents touch `auth.py` and `auth_middleware.py`. It automatically generates a structured conflict report:

```
Coordinator → All:  CONFLICT_REPORT
  conflict_id: "de63124c-..."
  category: "scope_overlap"
  severity: "medium"
```

**Phase 4 — AI-Driven Negotiation:**

Both agents are asked how to handle the conflict. Each independently calls Claude:

- **Alice:** "This is a critical security vulnerability. I should proceed first, then Bob can incorporate my changes into his refactoring."
- **Bob:** "Alice's security fix is urgent. My refactoring can wait. Let her go first, and I'll build on her changes."

Two independent AI agents, with no shared prompt and no hardcoded coordination logic, reached the same conclusion through the protocol's structured conflict channel.

**Phase 5 — Execution:**

Both agents plan and commit their operations through `OP_COMMIT`, carrying state references (`state_ref_before`, `state_ref_after`) and causal watermarks for auditability.

Total protocol messages: **10.** The entire coordination — from joining to conflict resolution to commit — happened through structured MPAC messages, not ad-hoc chat or manual human intervention.

## What MPAC Does *Not* Do

Being clear about boundaries is as important as explaining capabilities:

- **Not a transport protocol.** MPAC defines coordination semantics, not how messages are delivered. Use it over WebSocket, HTTP, message queues — whatever fits your infrastructure.
- **Not a state sync engine.** It doesn't replace CRDTs, OT, or version control. It coordinates *around* shared state, not the state itself.
- **Not a conflict resolution algorithm.** It provides the structured pipe — detection, reporting, escalation, resolution — but the actual decision logic is left to agents, arbiters, or policies.
- **Not a replacement for MCP or A2A.** It complements them. MCP handles tool invocation, A2A handles single-principal delegation, MPAC handles multi-principal coordination. They work at different layers.

## Current Status

MPAC is at **v0.1.7** — a draft protocol with working reference implementations but not yet a production standard.

What exists today:

- **Full protocol specification** ([SPEC.md](../SPEC.md)) — 30 sections covering all five layers, three security profiles, three compliance profiles, explicit consistency and execution models, normative state transition tables, and cross-lifecycle state machine rules.
- **Developer reference** ([MPAC_Developer_Reference.md](../MPAC_Developer_Reference.md)) — complete data dictionary with 10 core objects, 20 message types, 3 state machines with normative transition tables, and an implementation checklist.
- **JSON Schema** ([ref-impl/schema/](../ref-impl/schema/)) — machine-readable wire format definitions for envelope and all message payloads.
- **Reference implementations** in [Python](../ref-impl/python/) and [TypeScript](../ref-impl/typescript/) — ~90% protocol coverage (70 + 56 tests), 14-message cross-language interoperability, real Claude API end-to-end verification.
- **AI agent demo** ([ref-impl/demo/](../ref-impl/demo/)) — two Claude agents coordinating through the full protocol lifecycle, exercising session join, intent declaration, conflict detection, negotiation, commit, coordinator status, state snapshot, and session close.
- **Audit-driven evolution** — every version change is archived with rationale. The protocol has been through seven revision rounds including a five-dimension audit (v0.1.3→v0.1.4), a gap analysis (v0.1.4→v0.1.5), and a SOSP/OSDI-level deep review (v0.1.6→v0.1.7).

What's still missing:

- **Conformance test suite** — the interop tests exist but aren't yet a formal compliance certification.
- **v0.1.7 feature implementation** — `OP_BATCH_COMMIT`, pre-commit execution model, frozen scope progressive degradation, and coordinator accountability are specified but not yet implemented in reference code.
- **Authenticated security profile** — signature verification, replay detection, and role-based access are specified but not yet enforced in reference implementations.
- **Production deployment** — no known production system runs MPAC yet.
- **Formal verification** — the state machine interactions have normative transition tables but haven't been formally verified (e.g., TLA+).

MPAC is best suited today for research discussion, prototype implementations, and early ecosystem conversations about multi-agent coordination standards.

## Why Now

Three trends are converging that make multi-principal coordination increasingly urgent:

**Agents are gaining autonomy.** As AI agents move from "tool that answers questions" to "system that takes actions," the cost of uncoordinated concurrent action rises dramatically. Two chatbots giving conflicting advice is annoying; two autonomous agents overwriting each other's code changes is a real production incident.

**Multi-agent architectures are proliferating.** MCP and A2A have established that agents won't operate in isolation. But the more agents interact, the more likely they'll serve different principals with different goals — and the more urgent the need for coordination semantics that don't assume a single authority.

**Accountability requirements are tightening.** As agents make consequential decisions on behalf of people, the ability to trace *who instructed what, based on which information, and why* becomes a governance requirement, not a nice-to-have. MPAC's causal watermarking and structured conflict objects are designed to make this traceability a first-class protocol feature.

## Get Involved

MPAC is an open protocol in active development. If you're working on multi-agent systems, agent coordination frameworks, or collaborative AI applications, we'd welcome your perspective.

- **Read the spec:** [SPEC.md](../SPEC.md)
- **Try the reference implementations:** [Python](../ref-impl/python/) | [TypeScript](../ref-impl/typescript/)
- **Run the AI agent demo:** [ref-impl/demo/run_ai_agents.py](../ref-impl/demo/run_ai_agents.py)
- **Review the protocol evolution:** [version_history/CHANGELOG.md](../version_history/CHANGELOG.md)

The hardest problems in multi-agent coordination aren't about message formats — they're about deciding what coordination semantics are worth standardizing. That's a conversation that benefits from diverse perspectives. We're looking forward to yours.
