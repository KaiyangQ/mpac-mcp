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
    expires_at?: string;
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
    category: ConflictCategory;
    severity: Severity;
    involved_principals: string[];
    scope_a: any;
    scope_b: any;
    stateMachine: ConflictStateMachine;
    created_at: string;
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
    constructor(sessionId: string, securityProfile?: SecurityProfile, complianceProfile?: ComplianceProfile);
    /**
     * Process incoming message and generate responses
     */
    processMessage(envelope: MessageEnvelope): MessageEnvelope[];
    private handleHello;
    private handleIntentAnnounce;
    private handleOpPropose;
    private handleOpCommit;
    private handleConflictReport;
    private handleResolution;
    getParticipant(principalId: string): Principal | undefined;
    getIntent(intentId: string): Intent | undefined;
    getOperation(operationId: string): Operation | undefined;
    getConflict(conflictId: string): Conflict | undefined;
    getParticipants(): Principal[];
    getIntents(): Intent[];
    getOperations(): Operation[];
    getConflicts(): Conflict[];
}
export {};
//# sourceMappingURL=coordinator.d.ts.map