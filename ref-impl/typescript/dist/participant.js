import { MessageType } from "./models.js";
import { createEnvelope } from "./envelope.js";
import { LamportClock } from "./watermark.js";
export class Participant {
    principalId;
    principalType;
    displayName;
    roles;
    capabilities;
    lamportClock;
    constructor(principalId, principalType, displayName, roles = [], capabilities = []) {
        this.principalId = principalId;
        this.principalType = principalType;
        this.displayName = displayName;
        this.roles = roles;
        this.capabilities = capabilities;
        // Clock will be initialized when we start using it
        this.lamportClock = new LamportClock();
    }
    /**
     * Send HELLO message to join session
     */
    hello(sessionId) {
        const sender = {
            principal_id: this.principalId,
            principal_type: this.principalType,
        };
        const payload = {
            display_name: this.displayName,
            roles: this.roles,
            capabilities: this.capabilities,
        };
        return createEnvelope(MessageType.HELLO, sessionId, sender, payload);
    }
    /**
     * Announce intent
     */
    announceIntent(sessionId, intentId, objective, scope, expiryMs) {
        const sender = {
            principal_id: this.principalId,
            principal_type: this.principalType,
        };
        const watermark = this.lamportClock.createWatermark();
        const payload = {
            intent_id: intentId,
            objective,
            scope,
            expiry_ms: expiryMs,
        };
        return createEnvelope(MessageType.INTENT_ANNOUNCE, sessionId, sender, payload, watermark);
    }
    /**
     * Propose operation
     */
    proposeOp(sessionId, opId, intentId, target, opKind) {
        const sender = {
            principal_id: this.principalId,
            principal_type: this.principalType,
        };
        const watermark = this.lamportClock.createWatermark();
        const payload = {
            op_id: opId,
            intent_id: intentId,
            target,
            op_kind: opKind,
        };
        return createEnvelope(MessageType.OP_PROPOSE, sessionId, sender, payload, watermark);
    }
    /**
     * Commit operation
     */
    commitOp(sessionId, opId, intentId, target, opKind, stateRefBefore, stateRefAfter) {
        const sender = {
            principal_id: this.principalId,
            principal_type: this.principalType,
        };
        const watermark = this.lamportClock.createWatermark();
        const payload = {
            op_id: opId,
            intent_id: intentId,
            target,
            op_kind: opKind,
            state_ref_before: stateRefBefore,
            state_ref_after: stateRefAfter,
        };
        return createEnvelope(MessageType.OP_COMMIT, sessionId, sender, payload, watermark);
    }
    /**
     * Report conflict
     */
    reportConflict(sessionId, conflictId, category, severity, involvedPrincipals, scopeA, scopeB, details) {
        const sender = {
            principal_id: this.principalId,
            principal_type: this.principalType,
        };
        const watermark = this.lamportClock.createWatermark();
        const payload = {
            conflict_id: conflictId,
            category,
            severity,
            involved_principals: involvedPrincipals,
            scope_a: scopeA,
            scope_b: scopeB,
            basis: {},
            details,
        };
        return createEnvelope(MessageType.CONFLICT_REPORT, sessionId, sender, payload, watermark);
    }
    /**
     * Process received message and update Lamport clock
     */
    processMessage(envelope) {
        if (envelope.watermark) {
            this.lamportClock.processWatermark(envelope.watermark);
        }
    }
    /**
     * Get current Lamport clock value
     */
    getClockValue() {
        return this.lamportClock.value;
    }
    /**
     * Get participant info
     */
    getInfo() {
        return {
            principal_id: this.principalId,
            principal_type: this.principalType,
            display_name: this.displayName,
            roles: this.roles,
            capabilities: this.capabilities,
        };
    }
}
//# sourceMappingURL=participant.js.map