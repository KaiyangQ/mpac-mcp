// Message Types
export var MessageType;
(function (MessageType) {
    MessageType["HELLO"] = "HELLO";
    MessageType["SESSION_INFO"] = "SESSION_INFO";
    MessageType["HEARTBEAT"] = "HEARTBEAT";
    MessageType["GOODBYE"] = "GOODBYE";
    MessageType["SESSION_CLOSE"] = "SESSION_CLOSE";
    MessageType["COORDINATOR_STATUS"] = "COORDINATOR_STATUS";
    MessageType["INTENT_ANNOUNCE"] = "INTENT_ANNOUNCE";
    MessageType["INTENT_UPDATE"] = "INTENT_UPDATE";
    MessageType["INTENT_WITHDRAW"] = "INTENT_WITHDRAW";
    MessageType["INTENT_CLAIM"] = "INTENT_CLAIM";
    MessageType["OP_PROPOSE"] = "OP_PROPOSE";
    MessageType["OP_COMMIT"] = "OP_COMMIT";
    MessageType["OP_REJECT"] = "OP_REJECT";
    MessageType["OP_SUPERSEDE"] = "OP_SUPERSEDE";
    MessageType["CONFLICT_REPORT"] = "CONFLICT_REPORT";
    MessageType["CONFLICT_ACK"] = "CONFLICT_ACK";
    MessageType["CONFLICT_ESCALATE"] = "CONFLICT_ESCALATE";
    MessageType["RESOLUTION"] = "RESOLUTION";
    MessageType["PROTOCOL_ERROR"] = "PROTOCOL_ERROR";
})(MessageType || (MessageType = {}));
// Intent States
export var IntentState;
(function (IntentState) {
    IntentState["ANNOUNCED"] = "ANNOUNCED";
    IntentState["ACTIVE"] = "ACTIVE";
    IntentState["EXPIRED"] = "EXPIRED";
    IntentState["WITHDRAWN"] = "WITHDRAWN";
    IntentState["SUPERSEDED"] = "SUPERSEDED";
    IntentState["SUSPENDED"] = "SUSPENDED";
})(IntentState || (IntentState = {}));
// Operation States
export var OperationState;
(function (OperationState) {
    OperationState["PROPOSED"] = "PROPOSED";
    OperationState["COMMITTED"] = "COMMITTED";
    OperationState["REJECTED"] = "REJECTED";
    OperationState["ABANDONED"] = "ABANDONED";
    OperationState["FROZEN"] = "FROZEN";
})(OperationState || (OperationState = {}));
// Conflict States
export var ConflictState;
(function (ConflictState) {
    ConflictState["OPEN"] = "OPEN";
    ConflictState["ACKED"] = "ACKED";
    ConflictState["ESCALATED"] = "ESCALATED";
    ConflictState["RESOLVED"] = "RESOLVED";
    ConflictState["CLOSED"] = "CLOSED";
    ConflictState["DISMISSED"] = "DISMISSED";
})(ConflictState || (ConflictState = {}));
// Scope Kinds
export var ScopeKind;
(function (ScopeKind) {
    ScopeKind["FILE_SET"] = "file_set";
    ScopeKind["ENTITY_SET"] = "entity_set";
    ScopeKind["TASK_SET"] = "task_set";
})(ScopeKind || (ScopeKind = {}));
// Security Profiles
export var SecurityProfile;
(function (SecurityProfile) {
    SecurityProfile["OPEN"] = "open";
    SecurityProfile["AUTHENTICATED"] = "authenticated";
    SecurityProfile["VERIFIED"] = "verified";
})(SecurityProfile || (SecurityProfile = {}));
// Compliance Profiles
export var ComplianceProfile;
(function (ComplianceProfile) {
    ComplianceProfile["CORE"] = "core";
    ComplianceProfile["GOVERNANCE"] = "governance";
    ComplianceProfile["SEMANTIC"] = "semantic";
})(ComplianceProfile || (ComplianceProfile = {}));
// Credential Types
export var CredentialType;
(function (CredentialType) {
    CredentialType["BEARER_TOKEN"] = "bearer_token";
    CredentialType["MTLS_FINGERPRINT"] = "mtls_fingerprint";
    CredentialType["API_KEY"] = "api_key";
    CredentialType["X509_CHAIN"] = "x509_chain";
    CredentialType["CUSTOM"] = "custom";
})(CredentialType || (CredentialType = {}));
// Coordinator Events
export var CoordinatorEvent;
(function (CoordinatorEvent) {
    CoordinatorEvent["HEARTBEAT"] = "heartbeat";
    CoordinatorEvent["RECOVERED"] = "recovered";
    CoordinatorEvent["HANDOVER"] = "handover";
    CoordinatorEvent["ASSUMED"] = "assumed";
})(CoordinatorEvent || (CoordinatorEvent = {}));
// Session Health
export var SessionHealth;
(function (SessionHealth) {
    SessionHealth["HEALTHY"] = "healthy";
    SessionHealth["DEGRADED"] = "degraded";
    SessionHealth["RECOVERING"] = "recovering";
})(SessionHealth || (SessionHealth = {}));
// Session Close Reason
export var SessionCloseReason;
(function (SessionCloseReason) {
    SessionCloseReason["COMPLETED"] = "completed";
    SessionCloseReason["TIMEOUT"] = "timeout";
    SessionCloseReason["POLICY"] = "policy";
    SessionCloseReason["COORDINATOR_SHUTDOWN"] = "coordinator_shutdown";
    SessionCloseReason["MANUAL"] = "manual";
})(SessionCloseReason || (SessionCloseReason = {}));
// Roles
export var Role;
(function (Role) {
    Role["OBSERVER"] = "observer";
    Role["CONTRIBUTOR"] = "contributor";
    Role["REVIEWER"] = "reviewer";
    Role["OWNER"] = "owner";
    Role["ARBITER"] = "arbiter";
})(Role || (Role = {}));
// Conflict Categories
export var ConflictCategory;
(function (ConflictCategory) {
    ConflictCategory["SCOPE_OVERLAP"] = "scope_overlap";
    ConflictCategory["CONCURRENT_WRITE"] = "concurrent_write";
    ConflictCategory["SEMANTIC_GOAL_CONFLICT"] = "semantic_goal_conflict";
    ConflictCategory["ASSUMPTION_CONTRADICTION"] = "assumption_contradiction";
    ConflictCategory["POLICY_VIOLATION"] = "policy_violation";
    ConflictCategory["AUTHORITY_CONFLICT"] = "authority_conflict";
    ConflictCategory["DEPENDENCY_BREAKAGE"] = "dependency_breakage";
    ConflictCategory["RESOURCE_CONTENTION"] = "resource_contention";
})(ConflictCategory || (ConflictCategory = {}));
// Severity
export var Severity;
(function (Severity) {
    Severity["INFO"] = "info";
    Severity["LOW"] = "low";
    Severity["MEDIUM"] = "medium";
    Severity["HIGH"] = "high";
    Severity["CRITICAL"] = "critical";
})(Severity || (Severity = {}));
// Decision
export var Decision;
(function (Decision) {
    Decision["APPROVED"] = "approved";
    Decision["REJECTED"] = "rejected";
    Decision["DISMISSED"] = "dismissed";
    Decision["HUMAN_OVERRIDE"] = "human_override";
    Decision["POLICY_OVERRIDE"] = "policy_override";
    Decision["MERGED"] = "merged";
    Decision["DEFERRED"] = "deferred";
})(Decision || (Decision = {}));
// Error Codes
export var ErrorCode;
(function (ErrorCode) {
    ErrorCode["MALFORMED_MESSAGE"] = "malformed_message";
    ErrorCode["UNKNOWN_MESSAGE_TYPE"] = "unknown_message_type";
    ErrorCode["INVALID_REFERENCE"] = "invalid_reference";
    ErrorCode["VERSION_MISMATCH"] = "version_mismatch";
    ErrorCode["CAPABILITY_UNSUPPORTED"] = "capability_unsupported";
    ErrorCode["AUTHORIZATION_FAILED"] = "authorization_failed";
    ErrorCode["PARTICIPANT_UNAVAILABLE"] = "participant_unavailable";
    ErrorCode["RESOLUTION_TIMEOUT"] = "resolution_timeout";
    ErrorCode["SCOPE_FROZEN"] = "scope_frozen";
    ErrorCode["CLAIM_CONFLICT"] = "claim_conflict";
    ErrorCode["COORDINATOR_CONFLICT"] = "coordinator_conflict";
    ErrorCode["STATE_DIVERGENCE"] = "state_divergence";
    ErrorCode["SESSION_CLOSED"] = "session_closed";
    ErrorCode["CREDENTIAL_REJECTED"] = "credential_rejected";
})(ErrorCode || (ErrorCode = {}));
//# sourceMappingURL=models.js.map