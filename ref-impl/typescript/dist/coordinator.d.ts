import { Principal, SecurityProfile, ComplianceProfile, ConflictCategory, Severity } from "./models.js";
import { MessageEnvelope } from "./envelope.js";
import { IntentStateMachine, OperationStateMachine, ConflictStateMachine } from "./state-machines.js";
interface Intent {
    intent_id: string;
    principal_id: string;
    objective: string;
    scope: any;
    stateMachine: IntentStateMachine;
    created_at: string;
    received_at: number;
    ttl_sec?: number;
    expires_at?: number;
    last_message_id?: string;
    claimed_by?: string;
}
interface Operation {
    op_id: string;
    intent_id: string;
    principal_id: string;
    target: string;
    op_kind: string;
    stateMachine: OperationStateMachine;
    created_at: string;
}
interface Conflict {
    conflict_id: string;
    category: ConflictCategory | string;
    severity: Severity | string;
    involved_principals: string[];
    scope_a: any;
    scope_b: any;
    intent_a: string;
    intent_b: string;
    stateMachine: ConflictStateMachine;
    created_at: number;
    related_intents: string[];
    related_ops: string[];
    escalated_to?: string;
    escalated_at?: number;
}
interface ParticipantInfo {
    principal: Principal;
    last_seen: number;
    status: string;
    is_available: boolean;
}
export declare class SessionCoordinator {
    private sessionId;
    private coordinatorId;
    private securityProfile;
    private complianceProfile;
    private participants;
    private intents;
    private operations;
    private conflicts;
    private lamportClock;
    private createdAt;
    private intentExpiryGraceSec;
    private unavailabilityTimeoutMs;
    private resolutionTimeoutMs;
    private claims;
    constructor(sessionId: string, securityProfile?: SecurityProfile, complianceProfile?: ComplianceProfile, intentExpiryGraceSec?: number, unavailabilityTimeoutSec?: number, resolutionTimeoutSec?: number);
    processMessage(envelope: MessageEnvelope): MessageEnvelope[];
    checkExpiry(nowMs?: number): MessageEnvelope[];
    checkLiveness(nowMs?: number): MessageEnvelope[];
    checkResolutionTimeouts(nowMs?: number): MessageEnvelope[];
    private handleHello;
    private handleHeartbeat;
    private handleGoodbye;
    private handleIntentAnnounce;
    private handleIntentUpdate;
    private handleIntentWithdraw;
    private handleIntentClaim;
    private handleOpPropose;
    private handleOpCommit;
    private handleConflictReport;
    private handleConflictAck;
    private handleConflictEscalate;
    private handleResolution;
    private cascadeIntentTermination;
    private checkAutoDismiss;
    private handleParticipantUnavailable;
    private makeEnvelope;
    private makeOpReject;
    private detectScopeOverlaps;
    private findArbiter;
    getParticipant(id: string): ParticipantInfo | undefined;
    getIntent(id: string): Intent | undefined;
    getOperation(id: string): Operation | undefined;
    getConflict(id: string): Conflict | undefined;
    getParticipants(): ParticipantInfo[];
    getIntents(): Intent[];
    getOperations(): Operation[];
    getConflicts(): Conflict[];
}
export {};
//# sourceMappingURL=coordinator.d.ts.map