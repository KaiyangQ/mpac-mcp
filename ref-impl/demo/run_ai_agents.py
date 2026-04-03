#!/usr/bin/env python3
"""
MPAC Live Demo — Two AI agents (Claude) coordinate through the MPAC protocol.

Scenario: A Python web project needs refactoring. Two agents independently decide
what to work on, announce intents, and the coordinator detects conflicts when
their scopes overlap. The agents then negotiate through the protocol.
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

from ai_agent import AIAgent
from mpac.coordinator import SessionCoordinator

SESSION_ID = "live-ai-session-001"

PROJECT_CONTEXT = """
A Python web application (Flask) with the following structure:

  src/
    app.py              — Flask app factory, route registration
    auth.py             — Authentication: login, logout, token validation
    auth_middleware.py   — Request authentication middleware
    models.py           — SQLAlchemy models: User, Session, Permission
    database.py         — Database connection, migration helpers
    api/
      users.py          — User CRUD API endpoints
      admin.py          — Admin panel API endpoints
    utils/
      validators.py     — Input validation utilities
      crypto.py         — Password hashing, token generation

Known issues:
1. auth.py has a security bug: tokens aren't validated for expiry
2. models.py User model is missing email uniqueness constraint
3. api/users.py has N+1 query problem on GET /users
4. auth_middleware.py duplicates logic from auth.py
5. validators.py lacks proper email format checking
"""

# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def print_phase(title):
    w = 64
    print(f"\n{'═' * w}")
    print(f"  {title}")
    print(f"{'═' * w}\n")

def print_message(label, envelope, indent=2):
    prefix = " " * indent
    mt = envelope.get("message_type", "?")
    sender = envelope.get("sender", {}).get("principal_id", "?")
    print(f"{prefix}[{mt}] from {sender}")
    payload = envelope.get("payload", {})
    for k, v in payload.items():
        val_str = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
        if len(val_str) > 100:
            val_str = val_str[:97] + "..."
        print(f"{prefix}  {k}: {val_str}")

def print_agent_decision(agent_name, decision, label="Decision"):
    print(f"  🤖 {agent_name} {label}:")
    for k, v in decision.items():
        val_str = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
        print(f"      {k}: {val_str}")


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

def main():
    print_phase("MPAC Live Demo — AI Agent Coordination")
    print(f"  Session: {SESSION_ID}")
    print(f"  Scenario: Two AI agents independently decide how to fix a Python web app.")
    print(f"  Protocol: MPAC v0.1.4 with coordinator-managed conflict detection.\n")

    # ---- Setup ----
    coordinator = SessionCoordinator(SESSION_ID)

    agent_a = AIAgent(
        name="Alice",
        role_description="You are a security-focused engineer. You care most about auth, tokens, and access control.",
        session_id=SESSION_ID,
    )
    agent_b = AIAgent(
        name="Bob",
        role_description="You are a code quality engineer. You care about eliminating duplication. You noticed auth_middleware.py duplicates logic from auth.py, and models.py User model is incomplete. You want to refactor auth and models.",
        session_id=SESSION_ID,
    )

    transcript = []  # full message log

    def process(envelope, label=""):
        """Send envelope to coordinator, log everything."""
        transcript.append({"direction": "→ coordinator", "label": label, "envelope": envelope})
        responses = coordinator.process_message(envelope)
        for r in responses:
            transcript.append({"direction": "← coordinator", "label": "response", "envelope": r})
            print_message("  Response", r, indent=4)
        return responses

    # ════════════════ Phase 1: Join Session ════════════════
    print_phase("Phase 1: Session Join")

    for agent in [agent_a, agent_b]:
        print(f"  {agent.name} sends HELLO...")
        hello = agent.send_hello()
        print_message(f"  {agent.name}", hello)
        responses = process(hello, f"{agent.name} HELLO")
        print()

    # ════════════════ Phase 2: Intents ════════════════
    print_phase("Phase 2: AI Agents Decide & Announce Intents")

    print("  Asking Alice (security engineer) what she wants to work on...\n")
    alice_intent = agent_a.decide_intent(PROJECT_CONTEXT, [])
    print_agent_decision("Alice", alice_intent, "intent decision")
    print()

    alice_intent_msg = agent_a.send_intent(alice_intent)
    print_message("  Alice INTENT_ANNOUNCE", alice_intent_msg)
    alice_responses = process(alice_intent_msg, "Alice intent")
    print()

    # Bob sees Alice's intent before deciding
    alice_summary = {
        "agent": "Alice",
        "objective": alice_intent["objective"],
        "files": alice_intent.get("files", []),
    }

    print("  Asking Bob (performance engineer) what he wants to work on...\n")
    bob_intent = agent_b.decide_intent(PROJECT_CONTEXT, [alice_summary])
    print_agent_decision("Bob", bob_intent, "intent decision")
    print()

    bob_intent_msg = agent_b.send_intent(bob_intent)
    print_message("  Bob INTENT_ANNOUNCE", bob_intent_msg)
    bob_responses = process(bob_intent_msg, "Bob intent")
    print()

    # ════════════════ Phase 3: Conflict? ════════════════
    conflicts = [r for r in bob_responses if r.get("message_type") == "CONFLICT_REPORT"]

    if conflicts:
        print_phase("Phase 3: CONFLICT DETECTED — Agents Negotiate")

        for conflict_msg in conflicts:
            conflict_payload = conflict_msg.get("payload", {})
            conflict_id = conflict_payload.get("conflict_id", "unknown")
            print(f"  ⚠️  Conflict {conflict_id}")
            print(f"      Category: {conflict_payload.get('category')}")
            print(f"      Intents: {conflict_payload.get('intent_a')} vs {conflict_payload.get('intent_b')}")
            print()

            # Ask both agents how they want to handle this
            print("  Asking Alice how she wants to handle the conflict...\n")
            alice_response = agent_a.decide_on_conflict(conflict_payload, alice_intent, bob_intent)
            print_agent_decision("Alice", alice_response, "conflict response")
            print()

            print("  Asking Bob how he wants to handle the conflict...\n")
            bob_response = agent_b.decide_on_conflict(conflict_payload, bob_intent, alice_intent)
            print_agent_decision("Bob", bob_response, "conflict response")
            print()

            # Determine resolution based on agent responses
            alice_choice = alice_response.get("response", "proceed")
            bob_choice = bob_response.get("response", "proceed")

            print(f"  Resolution logic: Alice={alice_choice}, Bob={bob_choice}")

            if alice_choice == "yield":
                decision = "approved"  # approve Bob's intent
                rationale = f"Alice yielded. Reason: {alice_response.get('reasoning', 'N/A')}"
            elif bob_choice == "yield":
                decision = "approved"  # approve Alice's intent
                rationale = f"Bob yielded. Reason: {bob_response.get('reasoning', 'N/A')}"
            else:
                decision = "approved"  # both proceed, coordinator approves both
                rationale = f"Both agents chose to proceed. Alice: {alice_response.get('reasoning', 'N/A')}. Bob: {bob_response.get('reasoning', 'N/A')}"

            # Send RESOLUTION
            resolution = agent_a.participant.resolve_conflict(SESSION_ID, conflict_id, decision)
            print()
            print_message("  RESOLUTION", resolution)
            process(resolution, "resolution")
            print()
    else:
        print_phase("Phase 3: No Conflict — Clean Partition")
        print("  Both agents chose non-overlapping scopes. Protocol allows parallel execution.\n")

    # ════════════════ Phase 4: Operations ════════════════
    print_phase("Phase 4: AI Agents Plan & Commit Operations")

    print("  Asking Alice to plan her code operation...\n")
    alice_op = agent_a.plan_operation(alice_intent)
    print_agent_decision("Alice", alice_op, "operation plan")
    print()

    alice_commit = agent_a.send_op_commit(alice_intent, alice_op)
    print_message("  Alice OP_COMMIT", alice_commit)
    process(alice_commit, "Alice commit")
    print()

    print("  Asking Bob to plan his code operation...\n")
    bob_op = agent_b.plan_operation(bob_intent)
    print_agent_decision("Bob", bob_op, "operation plan")
    print()

    bob_commit = agent_b.send_op_commit(bob_intent, bob_op)
    print_message("  Bob OP_COMMIT", bob_commit)
    process(bob_commit, "Bob commit")
    print()

    # ════════════════ Summary ════════════════
    print_phase("Session Summary")
    print(f"  Total MPAC messages exchanged: {len(transcript)}")
    print(f"  Conflicts detected: {len(conflicts)}")
    print(f"  Alice's work: {alice_intent.get('objective', 'N/A')}")
    print(f"    Files: {alice_intent.get('files', [])}")
    print(f"  Bob's work: {bob_intent.get('objective', 'N/A')}")
    print(f"    Files: {bob_intent.get('files', [])}")

    # Overlap analysis
    alice_files = set(alice_intent.get("files", []))
    bob_files = set(bob_intent.get("files", []))
    overlap = alice_files & bob_files
    if overlap:
        print(f"\n  Overlapping files: {sorted(overlap)}")
        print(f"  Conflict was {'detected and resolved' if conflicts else 'NOT detected (bug?)'}.")
    else:
        print(f"\n  No file overlap — agents naturally partitioned work.")

    # Write full transcript
    transcript_path = os.path.join(os.path.dirname(__file__), "ai_demo_transcript.json")
    with open(transcript_path, "w") as f:
        json.dump(transcript, f, indent=2, ensure_ascii=False)
    print(f"\n  Full transcript: {transcript_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
