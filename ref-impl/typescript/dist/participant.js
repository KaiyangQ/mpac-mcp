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
    credential;
    constructor(principalId, principalType, displayName, roles = [], capabilities = [], credential) {
        this.principalId = principalId;
        this.principalType = principalType;
        this.displayName = displayName;
        this.roles = roles;
        this.capabilities = capabilities;
        this.lamportClock = new LamportClock();
        this.credential = credential;
    }
    sender() {
        return { principal_id: this.principalId, principal_type: this.principalType };
    }
    make(messageType, sessionId, payload) {
        return createEnvelope(messageType, sessionId, this.sender(), payload, this.lamportClock.createWatermark());
    }
    // ================================================================
    //  Session layer
    // ================================================================
    hello(sessionId) {
        const payload = {
            display_name: this.displayName, roles: this.roles, capabilities: this.capabilities,
        };
        if (this.credential)
            payload.credential = this.credential;
        return this.make(MessageType.HELLO, sessionId, payload);
    }
    heartbeat(sessionId, status = "idle", activeIntentId, summary) {
        const payload = { status };
        if (activeIntentId)
            payload.active_intent_id = activeIntentId;
        if (summary)
            payload.summary = summary;
        return this.make(MessageType.HEARTBEAT, sessionId, payload);
    }
    goodbye(sessionId, reason = "user_exit", activeIntents, intentDisposition = "withdraw") {
        const payload = { reason, intent_disposition: intentDisposition };
        if (activeIntents)
            payload.active_intents = activeIntents;
        return this.make(MessageType.GOODBYE, sessionId, payload);
    }
    // ================================================================
    //  Intent layer
    // ================================================================
    announceIntent(sessionId, intentId, objective, scope, expiryMs) {
        const payload = { intent_id: intentId, objective, scope, expiry_ms: expiryMs };
        return this.make(MessageType.INTENT_ANNOUNCE, sessionId, payload);
    }
    updateIntent(sessionId, intentId, opts = {}) {
        const payload = { intent_id: intentId };
        if (opts.objective !== undefined)
            payload.objective = opts.objective;
        if (opts.scope !== undefined)
            payload.scope = opts.scope;
        if (opts.ttl_sec !== undefined)
            payload.ttl_sec = opts.ttl_sec;
        return this.make(MessageType.INTENT_UPDATE, sessionId, payload);
    }
    withdrawIntent(sessionId, intentId, reason) {
        const payload = { intent_id: intentId };
        if (reason)
            payload.reason = reason;
        return this.make(MessageType.INTENT_WITHDRAW, sessionId, payload);
    }
    claimIntent(sessionId, claimId, originalIntentId, originalPrincipalId, newIntentId, objective, scope, justification) {
        const payload = {
            claim_id: claimId, original_intent_id: originalIntentId,
            original_principal_id: originalPrincipalId,
            new_intent_id: newIntentId, objective, scope,
        };
        if (justification)
            payload.justification = justification;
        return this.make(MessageType.INTENT_CLAIM, sessionId, payload);
    }
    // ================================================================
    //  Operation layer
    // ================================================================
    proposeOp(sessionId, opId, intentId, target, opKind) {
        return this.make(MessageType.OP_PROPOSE, sessionId, {
            op_id: opId, intent_id: intentId, target, op_kind: opKind,
        });
    }
    commitOp(sessionId, opId, intentId, target, opKind, stateRefBefore, stateRefAfter) {
        return this.make(MessageType.OP_COMMIT, sessionId, {
            op_id: opId, intent_id: intentId, target, op_kind: opKind,
            state_ref_before: stateRefBefore, state_ref_after: stateRefAfter,
        });
    }
    // ================================================================
    //  Conflict layer
    // ================================================================
    reportConflict(sessionId, conflictId, category, severity, involvedPrincipals, scopeA, scopeB, details) {
        return this.make(MessageType.CONFLICT_REPORT, sessionId, {
            conflict_id: conflictId, category, severity, involved_principals: involvedPrincipals,
            scope_a: scopeA, scope_b: scopeB, basis: {}, details,
        });
    }
    ackConflict(sessionId, conflictId, ackType = "seen") {
        return this.make(MessageType.CONFLICT_ACK, sessionId, { conflict_id: conflictId, ack_type: ackType });
    }
    escalateConflict(sessionId, conflictId, escalateTo, reason, context) {
        const payload = { conflict_id: conflictId, escalate_to: escalateTo, reason };
        if (context)
            payload.context = context;
        return this.make(MessageType.CONFLICT_ESCALATE, sessionId, payload);
    }
    resolveConflict(sessionId, conflictId, decision, rationale, outcome) {
        const payload = { conflict_id: conflictId, decision };
        if (rationale)
            payload.rationale = rationale;
        if (outcome)
            payload.outcome = outcome;
        return this.make(MessageType.RESOLUTION, sessionId, payload);
    }
    processMessage(envelope) {
        if (envelope.watermark)
            this.lamportClock.processWatermark(envelope.watermark);
    }
    getClockValue() { return this.lamportClock.value; }
    getInfo() {
        return {
            principal_id: this.principalId, principal_type: this.principalType,
            display_name: this.displayName, roles: this.roles, capabilities: this.capabilities,
        };
    }
}
//# sourceMappingURL=participant.js.map