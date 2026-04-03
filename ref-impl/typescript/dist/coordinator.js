import { v4 as uuidv4 } from "uuid";
import { MessageType, SecurityProfile, ComplianceProfile, IntentState, OperationState, ConflictState, ConflictCategory, Severity, } from "./models.js";
import { createEnvelope } from "./envelope.js";
import { LamportClock } from "./watermark.js";
import { scopeOverlap } from "./scope.js";
import { IntentStateMachine, OperationStateMachine, ConflictStateMachine, } from "./state-machines.js";
export class SessionCoordinator {
    sessionId;
    coordinatorId = "coordinator-" + uuidv4();
    securityProfile;
    complianceProfile;
    participants = new Map();
    intents = new Map();
    operations = new Map();
    conflicts = new Map();
    lamportClock;
    createdAt;
    constructor(sessionId, securityProfile = SecurityProfile.OPEN, complianceProfile = ComplianceProfile.CORE) {
        this.sessionId = sessionId;
        this.securityProfile = securityProfile;
        this.complianceProfile = complianceProfile;
        this.lamportClock = new LamportClock();
        this.createdAt = new Date().toISOString();
    }
    /**
     * Process incoming message and generate responses
     */
    processMessage(envelope) {
        const responses = [];
        // Update Lamport clock with received watermark
        if (envelope.watermark) {
            this.lamportClock.processWatermark(envelope.watermark);
        }
        switch (envelope.message_type) {
            case MessageType.HELLO:
                responses.push(...this.handleHello(envelope));
                break;
            case MessageType.INTENT_ANNOUNCE:
                responses.push(...this.handleIntentAnnounce(envelope));
                break;
            case MessageType.OP_PROPOSE:
                responses.push(...this.handleOpPropose(envelope));
                break;
            case MessageType.OP_COMMIT:
                responses.push(...this.handleOpCommit(envelope));
                break;
            case MessageType.CONFLICT_REPORT:
                responses.push(...this.handleConflictReport(envelope));
                break;
            case MessageType.RESOLUTION:
                responses.push(...this.handleResolution(envelope));
                break;
        }
        return responses;
    }
    handleHello(envelope) {
        const payload = envelope.payload;
        const principal = {
            principal_id: envelope.sender.principal_id,
            principal_type: envelope.sender.principal_type,
            display_name: payload.display_name,
            roles: payload.roles,
            capabilities: payload.capabilities,
            joined_at: new Date().toISOString(),
        };
        this.participants.set(principal.principal_id, principal);
        const sender = {
            principal_id: this.coordinatorId,
            principal_type: "coordinator",
        };
        const watermark = this.lamportClock.createWatermark();
        const sessionInfoPayload = {
            session_id: this.sessionId,
            coordinator_principal_id: this.coordinatorId,
            created_at: this.createdAt,
            security_profile: this.securityProfile,
            compliance_profile: this.complianceProfile,
            participants: Array.from(this.participants.values()),
        };
        const response = createEnvelope(MessageType.SESSION_INFO, this.sessionId, sender, sessionInfoPayload, watermark);
        return [response];
    }
    handleIntentAnnounce(envelope) {
        const payload = envelope.payload;
        const intentId = payload.intent_id;
        const principalId = envelope.sender.principal_id;
        const intent = {
            intent_id: intentId,
            principal_id: principalId,
            objective: payload.objective,
            scope: payload.scope,
            stateMachine: new IntentStateMachine(IntentState.ANNOUNCED),
            created_at: new Date().toISOString(),
        };
        if (payload.expiry_ms) {
            intent.expires_at = new Date(Date.now() + payload.expiry_ms).toISOString();
        }
        this.intents.set(intentId, intent);
        // Auto-activate the intent
        intent.stateMachine.transition("activate");
        const responses = [];
        // Check for scope overlaps with other active intents
        for (const existingIntent of this.intents.values()) {
            if (existingIntent.intent_id !== intentId &&
                existingIntent.stateMachine.currentState === IntentState.ACTIVE) {
                if (scopeOverlap(intent.scope, existingIntent.scope)) {
                    // Auto-generate CONFLICT_REPORT
                    const conflictId = "conflict-" + uuidv4();
                    const conflict = {
                        conflict_id: conflictId,
                        category: ConflictCategory.SCOPE_OVERLAP,
                        severity: Severity.MEDIUM,
                        involved_principals: [principalId, existingIntent.principal_id],
                        scope_a: intent.scope,
                        scope_b: existingIntent.scope,
                        stateMachine: new ConflictStateMachine(ConflictState.OPEN),
                        created_at: new Date().toISOString(),
                    };
                    this.conflicts.set(conflictId, conflict);
                    const sender = {
                        principal_id: this.coordinatorId,
                        principal_type: "coordinator",
                    };
                    const watermark = this.lamportClock.createWatermark();
                    const conflictPayload = {
                        conflict_id: conflictId,
                        category: ConflictCategory.SCOPE_OVERLAP,
                        severity: Severity.MEDIUM,
                        involved_principals: conflict.involved_principals,
                        scope_a: intent.scope,
                        scope_b: existingIntent.scope,
                        basis: {
                            intent_id: intentId,
                        },
                        details: `Intent ${intentId} overlaps with intent ${existingIntent.intent_id}`,
                    };
                    responses.push(createEnvelope(MessageType.CONFLICT_REPORT, this.sessionId, sender, conflictPayload, watermark));
                }
            }
        }
        return responses;
    }
    handleOpPropose(envelope) {
        const payload = envelope.payload;
        const opId = payload.op_id;
        const principalId = envelope.sender.principal_id;
        const operation = {
            op_id: opId,
            intent_id: payload.intent_id,
            principal_id: principalId,
            target: payload.target,
            op_kind: payload.op_kind,
            stateMachine: new OperationStateMachine(OperationState.PROPOSED),
            created_at: new Date().toISOString(),
        };
        this.operations.set(opId, operation);
        return [];
    }
    handleOpCommit(envelope) {
        const payload = envelope.payload;
        const opId = payload.op_id;
        const operation = this.operations.get(opId);
        if (operation) {
            operation.stateMachine.transition("commit");
        }
        return [];
    }
    handleConflictReport(envelope) {
        const payload = envelope.payload;
        const conflictId = payload.conflict_id;
        const conflict = {
            conflict_id: conflictId,
            category: payload.category,
            severity: payload.severity,
            involved_principals: payload.involved_principals,
            scope_a: payload.scope_a,
            scope_b: payload.scope_b,
            stateMachine: new ConflictStateMachine(ConflictState.OPEN),
            created_at: new Date().toISOString(),
        };
        this.conflicts.set(conflictId, conflict);
        return [];
    }
    handleResolution(envelope) {
        const payload = envelope.payload;
        const conflictId = payload.conflict_id;
        const conflict = this.conflicts.get(conflictId);
        if (conflict) {
            conflict.stateMachine.transition("resolve");
            conflict.stateMachine.transition("close");
        }
        return [];
    }
    // Accessors for testing
    getParticipant(principalId) {
        return this.participants.get(principalId);
    }
    getIntent(intentId) {
        return this.intents.get(intentId);
    }
    getOperation(operationId) {
        return this.operations.get(operationId);
    }
    getConflict(conflictId) {
        return this.conflicts.get(conflictId);
    }
    getParticipants() {
        return Array.from(this.participants.values());
    }
    getIntents() {
        return Array.from(this.intents.values());
    }
    getOperations() {
        return Array.from(this.operations.values());
    }
    getConflicts() {
        return Array.from(this.conflicts.values());
    }
}
//# sourceMappingURL=coordinator.js.map