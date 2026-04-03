export declare enum MessageType {
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
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
}
export declare enum IntentState {
    ANNOUNCED = "ANNOUNCED",
    ACTIVE = "ACTIVE",
    EXPIRED = "EXPIRED",
    WITHDRAWN = "WITHDRAWN",
    SUPERSEDED = "SUPERSEDED",
    SUSPENDED = "SUSPENDED"
}
export declare enum OperationState {
    PROPOSED = "PROPOSED",
    COMMITTED = "COMMITTED",
    REJECTED = "REJECTED",
    ABANDONED = "ABANDONED",
    FROZEN = "FROZEN"
}
export declare enum ConflictState {
    OPEN = "OPEN",
    ACKED = "ACKED",
    ESCALATED = "ESCALATED",
    RESOLVED = "RESOLVED",
    CLOSED = "CLOSED",
    DISMISSED = "DISMISSED"
}
export declare enum ScopeKind {
    FILE_SET = "file_set",
    ENTITY_SET = "entity_set",
    TASK_SET = "task_set"
}
export declare enum SecurityProfile {
    OPEN = "open",
    AUTHENTICATED = "authenticated",
    VERIFIED = "verified"
}
export declare enum ComplianceProfile {
    CORE = "core",
    GOVERNANCE = "governance",
    SEMANTIC = "semantic"
}
export declare enum Role {
    OBSERVER = "observer",
    CONTRIBUTOR = "contributor",
    REVIEWER = "reviewer",
    OWNER = "owner",
    ARBITER = "arbiter"
}
export declare enum ConflictCategory {
    SCOPE_OVERLAP = "scope_overlap",
    CONCURRENT_WRITE = "concurrent_write",
    SEMANTIC_GOAL_CONFLICT = "semantic_goal_conflict",
    ASSUMPTION_CONTRADICTION = "assumption_contradiction",
    POLICY_VIOLATION = "policy_violation",
    AUTHORITY_CONFLICT = "authority_conflict",
    DEPENDENCY_BREAKAGE = "dependency_breakage",
    RESOURCE_CONTENTION = "resource_contention"
}
export declare enum Severity {
    INFO = "info",
    LOW = "low",
    MEDIUM = "medium",
    HIGH = "high",
    CRITICAL = "critical"
}
export declare enum Decision {
    APPROVED = "approved",
    REJECTED = "rejected",
    DISMISSED = "dismissed",
    HUMAN_OVERRIDE = "human_override",
    POLICY_OVERRIDE = "policy_override",
    MERGED = "merged",
    DEFERRED = "deferred"
}
export declare enum ErrorCode {
    MALFORMED_MESSAGE = "malformed_message",
    UNKNOWN_MESSAGE_TYPE = "unknown_message_type",
    INVALID_REFERENCE = "invalid_reference",
    VERSION_MISMATCH = "version_mismatch",
    CAPABILITY_UNSUPPORTED = "capability_unsupported",
    AUTHORIZATION_FAILED = "authorization_failed",
    PARTICIPANT_UNAVAILABLE = "participant_unavailable",
    RESOLUTION_TIMEOUT = "resolution_timeout",
    SCOPE_FROZEN = "scope_frozen",
    CLAIM_CONFLICT = "claim_conflict"
}
export interface Principal {
    principal_id: string;
    principal_type: string;
    display_name?: string;
    roles?: Role[];
    capabilities?: string[];
    joined_at?: string;
}
export interface Sender {
    principal_id: string;
    principal_type: string;
}
export interface Watermark {
    kind: string;
    value: number | Record<string, number> | string;
    lamport_value?: number;
}
export interface Scope {
    kind: ScopeKind | string;
    resources?: string[];
    entities?: string[];
    task_ids?: string[];
    pattern?: string;
    expression?: string;
    language?: string;
    canonical_uris?: string[];
    extensions?: Record<string, unknown>;
}
export interface Basis {
    kind?: string;
    rule_id?: string;
    matcher?: string;
    match_type?: string;
    confidence?: number;
    matched_pair?: {
        left: {
            source_intent_id: string;
            content: string;
        };
        right: {
            source_intent_id: string;
            content: string;
        };
    };
    explanation?: string;
    intent_id?: string;
    op_id?: string;
    prior_scope?: Scope;
    prior_outcome?: Outcome;
}
export interface Outcome {
    accepted?: string[];
    rejected?: string[];
    merged?: string[];
    rollback?: string;
}
export interface GovernancePolicy {
    approval_required?: boolean;
    auto_resolve_conflicts?: boolean;
    conflict_resolution_timeout_ms?: number;
    intent_expiry_ms?: number;
}
export interface LivenessPolicy {
    heartbeat_interval_ms?: number;
    session_timeout_ms?: number;
    participant_timeout_ms?: number;
}
export interface SessionConfig {
    session_id: string;
    security_profile?: SecurityProfile;
    compliance_profile?: ComplianceProfile;
    governance_policy?: GovernancePolicy;
    liveness_policy?: LivenessPolicy;
}
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
//# sourceMappingURL=models.d.ts.map