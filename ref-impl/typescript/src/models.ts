// Message Types
export enum MessageType {
  HELLO = "HELLO",
  SESSION_INFO = "SESSION_INFO",
  HEARTBEAT = "HEARTBEAT",
  GOODBYE = "GOODBYE",
  INTENT_ANNOUNCE = "INTENT_ANNOUNCE",
  INTENT_UPDATE = "INTENT_UPDATE",
  INTENT_WITHDRAW = "INTENT_WITHDRAW",
  INTENT_CLAIM = "INTENT_CLAIM",
  OP_PROPOSE = "OP_PROPOSE",
  OP_COMMIT = "OP_COMMIT",
  OP_REJECT = "OP_REJECT",
  OP_SUPERSEDE = "OP_SUPERSEDE",
  CONFLICT_REPORT = "CONFLICT_REPORT",
  CONFLICT_ACK = "CONFLICT_ACK",
  CONFLICT_ESCALATE = "CONFLICT_ESCALATE",
  RESOLUTION = "RESOLUTION",
  PROTOCOL_ERROR = "PROTOCOL_ERROR",
}

// Intent States
export enum IntentState {
  ANNOUNCED = "ANNOUNCED",
  ACTIVE = "ACTIVE",
  EXPIRED = "EXPIRED",
  WITHDRAWN = "WITHDRAWN",
  SUPERSEDED = "SUPERSEDED",
  SUSPENDED = "SUSPENDED",
}

// Operation States
export enum OperationState {
  PROPOSED = "PROPOSED",
  COMMITTED = "COMMITTED",
  REJECTED = "REJECTED",
  ABANDONED = "ABANDONED",
  FROZEN = "FROZEN",
}

// Conflict States
export enum ConflictState {
  OPEN = "OPEN",
  ACKED = "ACKED",
  ESCALATED = "ESCALATED",
  RESOLVED = "RESOLVED",
  CLOSED = "CLOSED",
  DISMISSED = "DISMISSED",
}

// Scope Kinds
export enum ScopeKind {
  FILE_SET = "file_set",
  ENTITY_SET = "entity_set",
  TASK_SET = "task_set",
}

// Security Profiles
export enum SecurityProfile {
  OPEN = "open",
  AUTHENTICATED = "authenticated",
  VERIFIED = "verified",
}

// Compliance Profiles
export enum ComplianceProfile {
  CORE = "core",
  GOVERNANCE = "governance",
  SEMANTIC = "semantic",
}

// Roles
export enum Role {
  OBSERVER = "observer",
  CONTRIBUTOR = "contributor",
  REVIEWER = "reviewer",
  OWNER = "owner",
  ARBITER = "arbiter",
}

// Conflict Categories
export enum ConflictCategory {
  SCOPE_OVERLAP = "scope_overlap",
  CONCURRENT_WRITE = "concurrent_write",
  SEMANTIC_GOAL_CONFLICT = "semantic_goal_conflict",
  ASSUMPTION_CONTRADICTION = "assumption_contradiction",
  POLICY_VIOLATION = "policy_violation",
  AUTHORITY_CONFLICT = "authority_conflict",
  DEPENDENCY_BREAKAGE = "dependency_breakage",
  RESOURCE_CONTENTION = "resource_contention",
}

// Severity
export enum Severity {
  INFO = "info",
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
  CRITICAL = "critical",
}

// Decision
export enum Decision {
  APPROVED = "approved",
  REJECTED = "rejected",
  DISMISSED = "dismissed",
  HUMAN_OVERRIDE = "human_override",
  POLICY_OVERRIDE = "policy_override",
  MERGED = "merged",
  DEFERRED = "deferred",
}

// Error Codes
export enum ErrorCode {
  MALFORMED_MESSAGE = "malformed_message",
  UNKNOWN_MESSAGE_TYPE = "unknown_message_type",
  INVALID_REFERENCE = "invalid_reference",
  VERSION_MISMATCH = "version_mismatch",
  CAPABILITY_UNSUPPORTED = "capability_unsupported",
  AUTHORIZATION_FAILED = "authorization_failed",
  PARTICIPANT_UNAVAILABLE = "participant_unavailable",
  RESOLUTION_TIMEOUT = "resolution_timeout",
  SCOPE_FROZEN = "scope_frozen",
  CLAIM_CONFLICT = "claim_conflict",
}

// Principal
export interface Principal {
  principal_id: string;
  principal_type: string;
  display_name?: string;
  roles?: Role[];
  capabilities?: string[];
  joined_at?: string;
}

// Sender
export interface Sender {
  principal_id: string;
  principal_type: string;
}

// Watermark
export interface Watermark {
  kind: string;  // "lamport_clock" | "vector_clock" | "causal_frontier" | "opaque"
  value: number | Record<string, number> | string;  // depends on kind
  lamport_value?: number;  // fallback when kind != lamport_clock
}

// Scope
export interface Scope {
  kind: ScopeKind | string;
  resources?: string[];        // for file_set
  entities?: string[];         // for entity_set
  task_ids?: string[];         // for task_set
  pattern?: string;            // for resource_path
  expression?: string;         // for query
  language?: string;           // for query
  canonical_uris?: string[];
  extensions?: Record<string, unknown>;
}

// Basis
export interface Basis {
  kind?: string;  // "rule" | "heuristic" | "model_inference" | "semantic_match" | "human_report"
  rule_id?: string;
  matcher?: string;
  match_type?: string;  // "contradictory" | "equivalent" | "uncertain"
  confidence?: number;
  matched_pair?: { left: { source_intent_id: string; content: string }; right: { source_intent_id: string; content: string } };
  explanation?: string;
  intent_id?: string;
  op_id?: string;
  prior_scope?: Scope;
  prior_outcome?: Outcome;
}

// Outcome
export interface Outcome {
  accepted?: string[];
  rejected?: string[];
  merged?: string[];
  rollback?: string;
}

// Governance Policy
export interface GovernancePolicy {
  approval_required?: boolean;
  auto_resolve_conflicts?: boolean;
  conflict_resolution_timeout_ms?: number;
  intent_expiry_ms?: number;
}

// Liveness Policy
export interface LivenessPolicy {
  heartbeat_interval_ms?: number;
  session_timeout_ms?: number;
  participant_timeout_ms?: number;
}

// Session Config
export interface SessionConfig {
  session_id: string;
  security_profile?: SecurityProfile;
  compliance_profile?: ComplianceProfile;
  governance_policy?: GovernancePolicy;
  liveness_policy?: LivenessPolicy;
}

// Payload Types
export interface HelloPayload {
  display_name?: string;
  roles?: Role[];
  capabilities?: string[];
}

export interface SessionInfoPayload {
  session_id: string;
  coordinator_principal_id: string;
  created_at: string;
  security_profile: SecurityProfile;
  compliance_profile: ComplianceProfile;
  governance_policy?: GovernancePolicy;
  liveness_policy?: LivenessPolicy;
  participants: Principal[];
}

export interface IntentAnnouncePayload {
  intent_id: string;
  objective: string;
  scope: Scope;
  basis?: Basis;
  expiry_ms?: number;
  tags?: Record<string, string>;
}

export interface OpProposePayload {
  op_id: string;
  intent_id: string;
  target: string;
  op_kind: string;
  basis?: Basis;
  tags?: Record<string, string>;
}

export interface OpCommitPayload {
  op_id: string;
  intent_id: string;
  target: string;
  op_kind: string;
  state_ref_before?: string;
  state_ref_after?: string;
  basis?: Basis;
  tags?: Record<string, string>;
}

export interface ConflictReportPayload {
  conflict_id: string;
  category: ConflictCategory;
  severity: Severity;
  involved_principals: string[];
  scope_a: Scope;
  scope_b: Scope;
  basis: Basis;
  details?: string;
}

export interface ResolutionPayload {
  conflict_id: string;
  decision: Decision;
  resolved_principal_id: string;
  rationale?: string;
  outcome?: Outcome;
}

export interface IntentWithdrawPayload {
  intent_id: string;
  reason?: string;
}

export interface OpRejectPayload {
  op_id: string;
  reason: string;
  refers_to?: string;
}

export interface ProtocolErrorPayload {
  error_code: ErrorCode;
  message: string;
  details?: unknown;
  related_message_id?: string;
}
