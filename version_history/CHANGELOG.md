# MPAC Protocol Version History

## Directory Structure

```
version_history/
├── CHANGELOG.md                           ← this file
├── v0.1_baseline/                         ← original specification and review materials
├── v0.1.1_trust_governance_recovery/      ← first update round
├── v0.1.2_semantic_interop/               ← second update round
├── v0.1.3_interop_hardening/              ← v0.1.3 spec, audit report, reviews, update record
├── v0.1.4_state_machine_audit/            ← v0.1.4 spec, update record, protocol gap analysis
├── v0.1.5_coordinator_lifecycle_security/ ← v0.1.5 spec, update record
└── v0.1.6_p0_completion/                  ← v0.1.6 spec, update record
```

The current source of truth is always **SPEC.md** in the project root.

Companion documents in the project root (not versioned in this folder, always reflects the latest spec):
- **MPAC_Developer_Reference.md** — Developer-facing data dictionary: all data objects, field definitions, cross-entity references, state machines, enum registries, and implementation checklist. Updated in sync with SPEC.md.

---

## v0.1 — Baseline (2026-03-29)

The original MPAC v0.1 specification defining the core protocol: sessions, intents, operations, conflicts, governance, and causal context.

**Contents:**

| File | Description |
|------|-------------|
| `MPAC Specification v0.1.docx` | Original specification document (archived, not maintained) |
| `MPAC_Analysis_Report.docx` | Five-point comparison of MPAC vs MCP vs A2A |
| `MPAC_Critique_Response_Memo.docx` | Response to critical review identifying six gap areas |

---

## v0.1.1 — Trust, Governance, Failure Recovery (2026-03-31)

Addressed three shortcomings identified in the critique: trust enforcement, governance deadlock, and silent failure recovery.

**Key changes:**
- Section 23: Security Profiles (Open / Authenticated / Verified) with MUST-level requirements
- Sections 18.5–18.6: Arbiter designation, resolution timeout, frozen scope
- Section 14.4: Unavailability detection, SUSPENDED/ABANDONED states, INTENT_CLAIM message

**Contents:**

| File | Description |
|------|-------------|
| `SPEC_v0.1.1_2026-03-31.md` | Archived SPEC.md snapshot after this update |
| `MPAC Specification Update Record 2026-03-31.docx` | Detailed changelog for this round |
| `MPAC Critique Closure Note 2026-03-31.docx` | Closure note on critique response |

---

## v0.1.2 — Semantic Interoperability (2026-03-31)

Addressed the remaining gap: semantic interoperability across scope kinds and assumption matching.

**Key changes:**
- Sections 15.2.1–15.2.2: Canonical Resource URIs + Session Resource Registry
- Section 17.7.1: Standardized `semantic_match` basis output format
- Appendix A (Real-World Scenarios) removed from main spec (available in v0.1 baseline)

**Contents:**

| File | Description |
|------|-------------|
| `SPEC_v0.1.2_2026-04-01.md` | Archived SPEC.md snapshot of the final v0.1.2 spec |
| `MPAC Specification Update Record 2026-03-31 (Semantic Interoperability).docx` | Detailed changelog for this round |

---

## v0.1.3 — Interoperability Hardening (2026-04-01)

Comprehensive update addressing cross-implementation interoperability gaps, normative language tightening, and architectural clarifications identified through independent protocol review.

**Key changes:**
- Section 13.1: Payload schema tables for all 16 message types (required/optional fields, types, enums)
- Section 15.2.1: Mandatory scope overlap determination rules for `file_set`, `entity_set`, `task_set`
- Section 12.3: `lamport_clock` as MUST-support baseline watermark kind with comparison semantics and `lamport_value` fallback field
- Section 8.1: Session Coordinator defined as a first-class protocol entity
- Section 7.1: Intent-before-action upgraded to MUST in Governance Profile
- Section 7.3: Causal context upgraded to MUST for OP_COMMIT, CONFLICT_REPORT, RESOLUTION
- Section 16.3: `state_ref_before`/`state_ref_after` MUST in OP_COMMIT; `causally_unverifiable` handling
- Section 14.4.4: Concurrent INTENT_CLAIM resolution (first-claim-wins)
- Section 18.4: Rollback expectation requirement for rejecting committed operations; `winner`/`loser` shorthand removed
- Section 18.6.2: Frozen scope also rejects INTENT_ANNOUNCE; fallback timeout mechanism (Section 18.6.2.1)
- Section 23.1.2: Replay protection upgraded to MUST; role assertion validation added
- Section 23.4: End-to-end encryption consideration added
- Multiple SHOULD → MUST upgrades (ts format, HELLO, resolution watermark, conflict based_on_watermark)

**Contents:**

| File | Description |
|------|-------------|
| `SPEC_v0.1.3_2026-04-02.md` | Archived SPEC.md snapshot of the final v0.1.3 spec |
| `MPAC_v0.1.3_Update_Record.md` | Detailed changelog with rationale for each change |
| `MPAC_v0.1.3_Audit_Report.md` | Five-dimension audit of v0.1.3: efficiency, robustness, scalability, semantic alignment, state machine cross-safety |
| `MPAC_Independent_Review_2026-04-01.md` | Independent protocol review identifying interoperability gaps |
| `MPAC_Re-evaluation_v0.1.3_2026-04-01.md` | Re-evaluation after interoperability hardening |

---

## v0.1.4 — State Machine Cross-Safety & Session Negotiation (2026-04-02)

Spec revision driven by the v0.1.3 five-dimension audit. Resolved state machine cross-lifecycle gaps (Intent Expiry Cascade, Conflict Auto-Dismiss), added coordinator fault recovery guidance, and introduced SESSION_INFO for session negotiation.

**Key changes:**
- Section 15.7 (new): Intent Expiry Cascade — intent terminal → associated PROPOSED ops auto-reject, SUSPENDED → ops FROZEN
- Section 17.9 (new): Conflict Auto-Dismissal — all related intents and ops terminal → conflict auto-DISMISS, frozen scope released
- Section 8.1.1 (new): Coordinator Fault Recovery — state persistence SHOULD, restart state rebuild, participant behavior during coordinator unavailability
- Section 14.2 (new): SESSION_INFO message type — coordinator response to HELLO with session config and compatibility check
- Multiple normative upgrades from audit recommendations

**Protocol gap analysis (2026-04-03):** After completing ~85% reference implementation coverage (16/17 message types, full state machine lifecycle, liveness, arbiter workflow, intent claim), six protocol-level design gaps were identified for future spec revisions.

**Contents:**

| File | Description |
|------|-------------|
| `SPEC_v0.1.4_2026-04-02.md` | SPEC.md snapshot of the current v0.1.4 spec |
| `MPAC_v0.1.4_Update_Record.md` | Detailed changelog: what was resolved from audit, what was deferred, and why |
| `MPAC_v0.1.4_Gap_Analysis.md` | Protocol-level gap analysis: 6 design gaps identified after reference implementation |

---

## v0.1.5 — Coordinator Fault Tolerance, Session Lifecycle, Security Trust Establishment (2026-04-03)

Protocol-level revision driven by the v0.1.4 gap analysis. Addresses three of six identified protocol design gaps: coordinator fault tolerance (the most critical structural gap), session lifecycle (no defined end for sessions), and security trust establishment (no concrete credential exchange mechanism).

**Key changes:**
- Section 8.1.1 (rewritten): Coordinator liveness via `COORDINATOR_STATUS` heartbeat, mandatory state snapshot format (JSON), recovery procedure (snapshot + audit log replay), planned/unplanned handover protocol, split-brain prevention via Lamport clock comparison
- Section 9.6 (new): Session lifecycle — `SESSION_CLOSE` conditions (manual, auto-close on completion, session TTL, coordinator shutdown), session summary, transcript export format, lifecycle policy
- Section 23.1.4 (new): Credential exchange in HELLO handshake — five credential types (bearer_token, mtls_fingerprint, api_key, x509_chain, custom), coordinator validation, CREDENTIAL_REJECTED error
- Section 23.1.5 (new): Role assignment and verification — four-step process (request → policy evaluation → grant → enforcement), role policy configuration format
- Section 23.1.6 (new): Key distribution and rotation — coordinator key in SESSION_INFO, participant key registry, rotation via HEARTBEAT, watermark integrity binding in Verified profile
- Two new message types: `SESSION_CLOSE`, `COORDINATOR_STATUS` (total: 19)
- Four new error codes: `COORDINATOR_CONFLICT`, `STATE_DIVERGENCE`, `SESSION_CLOSED`, `CREDENTIAL_REJECTED`
- Section 14.5–14.7 renumbered (old 14.5 → 14.7) with all cross-references updated

**Contents:**

| File | Description |
|------|-------------|
| `SPEC_v0.1.5_2026-04-03.md` | SPEC.md snapshot of the current v0.1.5 spec |
| `MPAC_v0.1.5_Update_Record.md` | Detailed changelog: gap analysis → resolution map, impact on reference implementations |

---

## v0.1.6 — P0 Completion: OP_SUPERSEDE, Fault Recovery, JSON Schema (2026-04-03)

Resolves all P0 priority items from v0.1.5's coverage assessment. After this version, all 19 message types have full handler implementations, the coordinator supports snapshot-based fault recovery with audit log replay, and machine-readable JSON Schema definitions cover all 11 message payload types.

**Key changes:**
- `OP_SUPERSEDE` handler implemented: validates superseded op is COMMITTED, transitions to SUPERSEDED state, chains state references, supports supersession chains
- `SUPERSEDED` added to `OperationState` enum and state machine (`COMMITTED → SUPERSEDED` transition)
- Coordinator fault recovery: `recover_from_snapshot()` restores all internal state (participants, intents, operations, conflicts, Lamport clock, session status); `replay_audit_log()` replays messages received after snapshot
- Audit log recording: all processed messages stored for replay on recovery
- JSON Schema: added `session_close.schema.json`, `coordinator_status.schema.json`, `op_supersede.schema.json`; updated `envelope.schema.json` with new message types
- Tests: Python 55 → 70 (+15), TypeScript 44 → 56 (+12)

**Contents:**

| File | Description |
|------|-------------|
| `SPEC_v0.1.6_2026-04-03.md` | SPEC.md snapshot of the v0.1.6 spec |
| `MPAC_v0.1.6_Update_Record.md` | Detailed changelog: P0 items → resolution, coverage impact |

---

## Archival Convention and Procedure

When the user says "归档" or "archive the spec" or "参考 version history 里的 readme 把现有 spec 归档", follow this procedure exactly:

### Step 1: Determine the new version number

- Read this CHANGELOG to find the latest version entry (e.g., `v0.1.4_state_machine_audit`)
- The new version number increments the patch version (e.g., `v0.1.4` → `v0.1.5`)
- If the user specifies a version number, use that instead

### Step 2: Determine the folder name suffix

- Ask the user for a short descriptive suffix, or infer from context (e.g., `interop_hardening`, `state_machine_audit`)
- Folder name format: `v{version}_{suffix}`

### Step 3: Create the archive folder

```
mkdir version_history/v{version}_{suffix}/
```

### Step 4: Archive the current SPEC.md

- Copy the **current** `SPEC.md` from the project root into the new folder
- Name it `SPEC_v{current_version}_{today's date YYYY-MM-DD}.md`
- Example: if current SPEC is v0.1.3 and today is 2026-04-02, the file is `SPEC_v0.1.3_2026-04-02.md`
- This snapshot captures the state **before** the upcoming changes

### Step 5: Add supporting documents

- If there is an audit report, changelog, or update record, copy or create it in the same folder
- Common file types:
  - `MPAC_v{version}_Audit_Report.md` — external review or audit
  - `MPAC_v{version}_Update_Record.md` — detailed changelog with rationale
  - Other analysis documents as needed

### Step 6: Update this CHANGELOG

1. **Directory structure**: add the new folder to the tree at the top of this file
2. **Version entry**: add a new `## v{version} — {Title} ({date})` section before the "Convention" section, containing:
   - One-paragraph summary of what this version represents
   - `**Key changes:**` or `**Key findings:**` bullet list
   - `**Contents:**` table listing every file in the folder with a description
3. Keep entries in chronological order (newest last, just before this Convention section)

### Step 7: Apply changes to SPEC.md (if applicable)

- If the archive is in preparation for a spec revision, the user will instruct what changes to make to `SPEC.md` in the project root separately
- After changes are applied, the root `SPEC.md` should be updated to reflect the new version number in its Section 1

### Quick reference

| What | Where | Naming |
|------|-------|--------|
| Current source of truth | `SPEC.md` (project root) | Always `SPEC.md` |
| Pre-change snapshot | `version_history/v{new}/SPEC_v{old}_{date}.md` | Version = old spec version |
| Audit / review report | `version_history/v{new}/MPAC_v{old}_Audit_Report.md` | Version = spec being reviewed |
| Update record | `version_history/v{new}/MPAC_v{new}_Update_Record.md` | Version = new spec version |
| This index | `version_history/CHANGELOG.md` | Always `CHANGELOG.md` |
