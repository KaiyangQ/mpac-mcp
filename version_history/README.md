# MPAC Protocol Version History

## Directory Structure

```
version_history/
├── README.md                              ← this file
├── v0.1_baseline/                         ← original specification and review materials
├── v0.1.1_trust_governance_recovery/      ← first update round
├── v0.1.2_semantic_interop/               ← second update round
└── v0.1.3_interop_hardening/              ← third update round
```

The current source of truth is always **SPEC.md** in the project root.

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
| `SPEC_v0.1.2_2026-04-01.md` | Archived SPEC.md snapshot before this update |
| `MPAC_v0.1.3_Update_Record.md` | Detailed changelog with rationale for each change |

---

## Convention for Future Updates

Each new update should:
1. Archive the current SPEC.md as `SPEC_v{version}_{date}.md` in the new version folder
2. Create an update record docx describing what changed and why
3. Add an entry to this README
