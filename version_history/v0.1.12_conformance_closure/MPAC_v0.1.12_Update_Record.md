# MPAC v0.1.12 Update Record — Conformance Closure

**Date:** 2026-04-05
**Previous version:** v0.1.11
**Scope:** Schema conformance closure — no new message types, no new protocol semantics beyond standardizing the `authorization` coordinator event

---

## Motivation

An independent protocol audit identified that while the MPAC spec was mature at the design level, the "published artifact surface" (JSON Schema, examples, conditional constraints) had not fully closed against the spec prose. Specifically:

1. Only 13 of 21 message types had JSON Schema definitions
2. The envelope schema treated `payload` as a generic `object` with no message-type dispatch
3. `COORDINATOR_STATUS` had spec/schema/impl drift: missing `next_coordinator_epoch`, unregistered `authorization` event, extra `snapshot` field
4. `OP_BATCH_COMMIT` entry schema was looser than spec (missing required `state_ref_before`/`state_ref_after`)
5. `INTENT_CLAIM_STATUS` and `RESOLUTION.outcome` conditional constraints existed only in prose, not in schema
6. Demo transcript still used version `0.1.10`

---

## Changes

### P1 — Schema Completeness

**8 new message payload schemas added:**

| Schema | Required Fields | Notes |
|--------|----------------|-------|
| `heartbeat.schema.json` | `status` | Enum: idle, working, blocked, awaiting_review, offline |
| `goodbye.schema.json` | `reason` | Enum: user_exit, session_complete, error, timeout |
| `intent_claim.schema.json` | `claim_id`, `original_intent_id`, `original_principal_id`, `new_intent_id`, `objective`, `scope` | `scope` references shared Scope object |
| `intent_update.schema.json` | `intent_id` | At least one additional field SHOULD be present |
| `intent_withdraw.schema.json` | `intent_id` | |
| `op_reject.schema.json` | `op_id`, `reason` | |
| `conflict_ack.schema.json` | `conflict_id`, `ack_type` | Enum: seen, accepted, disputed |
| `conflict_escalate.schema.json` | `conflict_id`, `escalate_to`, `reason` | |

**Result:** 21 of 21 message types now have dedicated payload schemas.

### P1 — Envelope oneOf Dispatcher

The `envelope.schema.json` `payload` field now uses `allOf` with `if/then` clauses to dispatch payload validation to the correct message-specific schema based on `message_type`. Additionally, coordinator-authored messages (`SESSION_INFO`, `COORDINATOR_STATUS`, `INTENT_CLAIM_STATUS`, `OP_REJECT`, `CONFLICT_REPORT`, `RESOLUTION`, `PROTOCOL_ERROR`) now require `coordinator_epoch` via a conditional constraint.

### P1 — COORDINATOR_STATUS Alignment

- **`event` field:** Changed from free-form string to enum: `heartbeat`, `recovered`, `handover`, `assumed`, `authorization`. The `authorization` event was already emitted by both reference implementations for pre-commit operation approval; it is now standardized in the spec and schema.
- **`next_coordinator_epoch`:** Added to schema with `if/then` constraint requiring it when `event=handover` (already in spec, was missing from schema).
- **`authorization` fields:** `authorized_op_id` (required), `authorized_by` (required), and `authorized_batch_id` (optional) are now declared with an `if/then` constraint on `event=authorization`.
- **`snapshot` field:** Removed from schema. State snapshots are internal coordinator recovery artifacts, not part of the COORDINATOR_STATUS wire format. Recovery snapshots are transmitted via the snapshot mechanism defined in Section 8.1.1, not embedded in heartbeat messages.
- **SPEC.md updated:** Section 13.1 COORDINATOR_STATUS payload table now includes `authorization` event and its conditional fields (`authorized_op_id`, `authorized_batch_id`, `authorized_by`). The `successor_coordinator_id` and `next_coordinator_epoch` fields are re-classified from Optional (O) to Conditional (C).

### P2 — OP_BATCH_COMMIT Schema Tightening

Batch entry `required` array updated from `["op_id", "target", "op_kind"]` to `["op_id", "target", "op_kind", "state_ref_before", "state_ref_after"]`, matching the spec prose (Section 16.8) and aligning with `OP_COMMIT` schema.

### P2 — Conditional Schema Constraints

- **`INTENT_CLAIM_STATUS`:** Added `allOf` with three `if/then` clauses:
  - `decision=approved` → requires `new_intent_id`
  - `decision=rejected` → requires `reason`
  - `decision=withdrawn` → requires `reason`
  - Note: `approved_by` is required in Governance Profile but this is an implementation-level check (profile awareness is not encoded in JSON Schema)

- **`outcome.schema.json`:** The rollback requirement ("MUST when rejected list contains COMMITTED operations") depends on runtime operation state and cannot be fully expressed in JSON Schema. The constraint is documented in the schema `description` field; implementations MUST enforce it at runtime. An earlier draft included an `if/then` that required `rollback` whenever `rejected` was non-empty, but this was overly strict — rejecting intents or pre-commit proposals does not require rollback.

### P2 — Demo Transcript Version Fix

All `version` fields in `ai_demo_transcript.json` updated from `"0.1.10"` to `"0.1.12"`. All `protocol_version` fields similarly updated.

### Version Bump

All version strings updated to `0.1.12` across:
- `SPEC.md` (title, body, examples)
- `envelope.schema.json` (description)
- Python: `coordinator.py`, `envelope.py`, `__init__.py`, `pyproject.toml`, test assertions
- TypeScript: `coordinator.ts`, `envelope.ts`, `package.json`, `package-lock.json`
- Demo transcript: `ai_demo_transcript.json`

---

### Post-Draft Corrections

Three issues identified in review after the initial draft:

1. **Envelope `coordinator_epoch` constraint scope corrected:** The initial draft required `coordinator_epoch` on message types that are not coordinator-only. `CONFLICT_REPORT` and `RESOLUTION` can be sent by any participant/resolver; `OP_REJECT` can be sent by owner/arbiter participants; `PROTOCOL_ERROR` can be sent by participants (e.g. `CAUSAL_GAP`). All four removed. Added `SESSION_CLOSE` which is coordinator-only. Final list: `SESSION_INFO`, `SESSION_CLOSE`, `COORDINATOR_STATUS`, `INTENT_CLAIM_STATUS`.

2. **Authorization event missing required COORDINATOR_STATUS fields:** The initial standardization of `authorization` as a COORDINATOR_STATUS event introduced a schema requiring `coordinator_id` and `session_health`, but both reference implementations' `authorizeOperation` methods only populated the authorization-specific fields. Both implementations updated to include `coordinator_id` and `session_health` (computed from open conflict count), ensuring their output passes the schema they define.

3. **Outcome rollback `if/then` removed:** The initial draft added `if rejected non-empty then require rollback` to `outcome.schema.json`. This was overly strict — the spec only requires rollback when rejected items include COMMITTED operations, which is a runtime-state check. The constraint was moved to a descriptive annotation; implementations enforce it at runtime.

---

## Impact on Reference Implementations

Both reference implementations required a minor logic addition: the `authorizeOperation` method now includes `coordinator_id` and `session_health` in the authorization event payload, matching the COORDINATOR_STATUS schema requirements. All other changes were version string updates.

The `snapshot` field removed from the schema was never part of the COORDINATOR_STATUS wire format in either implementation — it was an artifact of schema documentation anticipating a recovery use case that is handled separately.

---

### Runtime Enforcement Hardening

A second audit pass identified 6 normative spec requirements that were not enforced at runtime in either reference implementation:

1. **HELLO-first gate:** Unregistered principals (except HELLO) now receive `AUTHORIZATION_FAILED`. GOODBYE is NOT exempt — an unregistered sender must not be able to trigger intent disposition via `active_intents`. Added at the top of `process_message` in both implementations.

2. **Credential validation:** Non-`open` security profiles now reject HELLO messages without a valid credential (`CREDENTIAL_REJECTED`). Added at the top of `_handle_hello` / `handleHello`.

3. **Resolution authority:** Pre-escalation conflicts can only be resolved by `owner` or `arbiter` roles. Post-escalation, only the `escalate_to` target or `arbiter` can resolve. Removed the `related_principal` / `relatedPrincipal` shortcut from `_is_authorized_resolver` / `isAuthorizedResolver`.

4. **Frozen-scope enforcement:** Per Section 18.6.1–18.6.2, scopes freeze only after `resolution_timeout_sec` expires and no arbiter is available — not immediately on conflict creation. A `scope_frozen` flag was added to the Conflict data structure, set by `check_resolution_timeouts` / `checkResolutionTimeouts`. `INTENT_ANNOUNCE`, `OP_PROPOSE`, `OP_COMMIT` (post-commit), and `OP_BATCH_COMMIT` now return `SCOPE_FROZEN` when the target scope overlaps with a frozen conflict's intent scopes. Added `_is_scope_frozen` / `isScopeFrozen` helper and four check points.

5. **Batch atomicity rollback:** `all_or_nothing` batches that fail validation now delete all already-registered operations from coordinator state before returning the batch reject. Previously, partially-created operations leaked into state.

6. **Error codes:** `CAUSAL_GAP` and `INTENT_BACKOFF` added to Python `ErrorCode` enum and TypeScript `ErrorCode` enum. `authorization` added to `CoordinatorEvent` enum in both languages.

**Existing test adjustments:** 9 pre-existing tests were adapted to the new enforcement rules — tests that committed/proposed operations while a conflict was active were reordered to commit before the conflict-creating announcement; tests that resolved conflicts with `contributor` role were updated to use `owner` role.

### P1 Enforcement Corrections (Second Audit Pass)

Three P1 issues were identified in the initial enforcement implementation and corrected within the same version:

1. **GOODBYE unauthenticated state-mutation path:** The initial implementation exempted GOODBYE from the HELLO-first gate, allowing an unregistered sender to force-withdraw other principals' intents via `active_intents`. Fix: removed GOODBYE exemption from the gate. Additionally, an ownership guard was added to `handleGoodbye` — the sender can only withdraw/transfer intents where `intent.principal_id == sender_id`.

2. **Frozen-scope triggers too early:** The initial implementation froze scopes on any non-terminal conflict, but Section 18.6.1–18.6.2 specifies that scopes freeze only after `resolution_timeout_sec` expires and no arbiter is available. Fix: added `scope_frozen: bool` field to the Conflict data structure (default `false`), set to `true` only by `check_resolution_timeouts` / `checkResolutionTimeouts` when no arbiter is found. The `_is_scope_frozen` / `isScopeFrozen` helper now checks the flag rather than testing for any active conflict.

3. **OP_BATCH_COMMIT bypasses frozen-scope:** The initial enforcement pass added frozen-scope checks to `INTENT_ANNOUNCE`, `OP_PROPOSE`, and `OP_COMMIT` but missed `OP_BATCH_COMMIT`. Fix: added frozen-scope check at the top of `_handle_op_batch_commit` / `handleOpBatchCommit`, rejecting the entire batch if the intent scope overlaps a frozen conflict.

### P1+P2 Enforcement Corrections (Third Audit Pass)

Four additional issues identified and corrected:

1. **OP_BATCH_COMMIT per-entry intent_id frozen-scope bypass:** The frozen-scope check only examined the top-level `intent_id`, but batch entries can carry their own `intent_id` that bypasses the check. Fix: both implementations now collect all unique intent_ids (top-level + per-entry) and check each against frozen scopes.

2. **scope_frozen not persisted in snapshot:** The snapshot serialization omitted `scope_frozen`, so coordinator recovery reset frozen conflicts to `false`. Fix: added `scope_frozen` to snapshot serialization in both implementations; recovery already read the field (defaulting to `false`), so no recovery-side change was needed in TypeScript; Python recovery now reads `scope_frozen` from snapshot data.

3. **INTENT_ANNOUNCE partial overlap too strict:** Section 18.6.2 specifies that `INTENT_ANNOUNCE` messages fully contained within frozen scope MUST be rejected, but partially overlapping scopes SHOULD be accepted with a warning. The implementation rejected any overlap. Fix: added `scope_contains` / `scopeContains` utility functions (check if all items in test scope are within container scope), `_check_frozen_scope_for_intent` / `checkFrozenScopeForIntent` methods that differentiate full containment from partial overlap, and `_build_frozen_union_scope` / `buildFrozenUnionScope` helpers that compute the union of two conflicting intents' scopes. Partially overlapping intents are now registered but receive a `PROTOCOL_ERROR(SCOPE_FROZEN)` warning with "Warning:" prefix.

4. **HELLO-first gate error code:** Section 14.1 specifies `INVALID_REFERENCE` for messages from unregistered participants, but both implementations returned `AUTHORIZATION_FAILED`. The adversarial tests had locked in the incorrect code. Fix: changed error code to `INVALID_REFERENCE` in both implementations and updated all test assertions.

### P1 Target-Based Frozen-Scope Correction (Fourth Audit Pass)

The third audit pass revealed a fundamental design flaw in the frozen-scope enforcement: all checks were intent-based (looking up the parent intent's scope), but `intent_id` is optional in the OP_PROPOSE, OP_COMMIT, and OP_BATCH_COMMIT schemas. Omitting `intent_id` entirely caused the frozen-scope guard to be skipped.

Fix: all frozen-scope checks for operations are now **target-based** — they construct a `file_set` scope from the operation's `target` field and check it directly against frozen conflict scopes. This aligns with the spec's Section 18.6.2 language: "OP_PROPOSE and OP_COMMIT messages targeting **resources within the frozen scope**".

1. **Python `_handle_op_propose`**: Changed from intent-based to target-based check. Previously only ran when `intent_id` was present; now always checks `target`.
2. **Python `_handle_op_commit`** (post-commit path): Same change — target-based instead of intent-based.
3. **Both `_handle_op_batch_commit` / `handleOpBatchCommit`**: Changed from collecting intent_ids to iterating each entry's `target` field. A batch with no `intent_id` at any level is now correctly blocked if any entry targets a frozen resource.
4. TypeScript single-op handlers (`handleOpPropose`, `handleOpCommit`) already used target-based checks and required no changes.

---

## Test Results

- Python: 109/109 tests passed (75 existing + 34 new adversarial enforcement tests)
- TypeScript: 88/88 tests passed (56 existing + 32 new adversarial enforcement tests)

New adversarial test files:
- `ref-impl/python/tests/test_v0112_enforcement.py` — 34 tests across 6 enforcement categories + target-based frozen-scope
- `ref-impl/typescript/tests/v0112-enforcement.test.ts` — 32 tests across 6 enforcement categories + target-based frozen-scope
