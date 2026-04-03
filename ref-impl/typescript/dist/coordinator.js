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
    intentExpiryGraceSec;
    unavailabilityTimeoutMs;
    resolutionTimeoutMs;
    claims = new Map(); // original_intent_id → claim_id
    constructor(sessionId, securityProfile = SecurityProfile.OPEN, complianceProfile = ComplianceProfile.CORE, intentExpiryGraceSec = 30, unavailabilityTimeoutSec = 90, resolutionTimeoutSec = 300) {
        this.sessionId = sessionId;
        this.securityProfile = securityProfile;
        this.complianceProfile = complianceProfile;
        this.lamportClock = new LamportClock();
        this.createdAt = new Date().toISOString();
        this.intentExpiryGraceSec = intentExpiryGraceSec;
        this.unavailabilityTimeoutMs = unavailabilityTimeoutSec * 1000;
        this.resolutionTimeoutMs = resolutionTimeoutSec * 1000;
    }
    // ================================================================
    //  Main message processing
    // ================================================================
    processMessage(envelope) {
        const responses = [];
        if (envelope.watermark) {
            this.lamportClock.processWatermark(envelope.watermark);
        }
        // Update liveness for sender
        const pid = envelope.sender.principal_id;
        const pInfo = this.participants.get(pid);
        if (pInfo)
            pInfo.last_seen = Date.now();
        switch (envelope.message_type) {
            case MessageType.HELLO:
                responses.push(...this.handleHello(envelope));
                break;
            case MessageType.HEARTBEAT:
                responses.push(...this.handleHeartbeat(envelope));
                break;
            case MessageType.GOODBYE:
                responses.push(...this.handleGoodbye(envelope));
                break;
            case MessageType.INTENT_ANNOUNCE:
                responses.push(...this.handleIntentAnnounce(envelope));
                break;
            case MessageType.INTENT_UPDATE:
                responses.push(...this.handleIntentUpdate(envelope));
                break;
            case MessageType.INTENT_WITHDRAW:
                responses.push(...this.handleIntentWithdraw(envelope));
                break;
            case MessageType.INTENT_CLAIM:
                responses.push(...this.handleIntentClaim(envelope));
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
            case MessageType.CONFLICT_ACK:
                responses.push(...this.handleConflictAck(envelope));
                break;
            case MessageType.CONFLICT_ESCALATE:
                responses.push(...this.handleConflictEscalate(envelope));
                break;
            case MessageType.RESOLUTION:
                responses.push(...this.handleResolution(envelope));
                break;
        }
        return responses;
    }
    // ================================================================
    //  Time-based lifecycle
    // ================================================================
    checkExpiry(nowMs) {
        const now = nowMs ?? Date.now();
        const allResponses = [];
        for (const intent of this.intents.values()) {
            if (intent.expires_at !== undefined &&
                !intent.stateMachine.isTerminal() &&
                intent.stateMachine.currentState !== IntentState.ANNOUNCED &&
                now >= intent.expires_at) {
                intent.stateMachine.transition("expire");
                allResponses.push(...this.cascadeIntentTermination(intent.intent_id));
            }
        }
        allResponses.push(...this.checkAutoDismiss());
        return allResponses;
    }
    checkLiveness(nowMs) {
        const now = nowMs ?? Date.now();
        const allResponses = [];
        for (const [pid, info] of this.participants) {
            if (!info.is_available || info.status === "offline")
                continue;
            if (now - info.last_seen > this.unavailabilityTimeoutMs) {
                info.is_available = false;
                allResponses.push(...this.handleParticipantUnavailable(pid));
            }
        }
        return allResponses;
    }
    checkResolutionTimeouts(nowMs) {
        const now = nowMs ?? Date.now();
        const allResponses = [];
        for (const conflict of this.conflicts.values()) {
            const st = conflict.stateMachine.currentState;
            if (st !== ConflictState.OPEN && st !== ConflictState.ACKED)
                continue;
            if (now - conflict.created_at <= this.resolutionTimeoutMs)
                continue;
            const arbiterId = this.findArbiter();
            if (arbiterId) {
                try {
                    if (st === ConflictState.OPEN)
                        conflict.stateMachine.transition("ack");
                    conflict.stateMachine.transition("escalate");
                }
                catch {
                    continue;
                }
                conflict.escalated_to = arbiterId;
                conflict.escalated_at = now;
                allResponses.push(this.makeEnvelope(MessageType.CONFLICT_ESCALATE, {
                    conflict_id: conflict.conflict_id,
                    escalate_to: arbiterId,
                    reason: "resolution_timeout",
                }));
            }
            else {
                allResponses.push(this.makeEnvelope(MessageType.PROTOCOL_ERROR, {
                    error_code: "RESOLUTION_TIMEOUT",
                    refers_to: conflict.conflict_id,
                    description: `No arbiter; conflict ${conflict.conflict_id} unresolved`,
                }));
            }
        }
        return allResponses;
    }
    // ================================================================
    //  Session layer handlers
    // ================================================================
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
        this.participants.set(principal.principal_id, {
            principal, last_seen: Date.now(), status: "idle", is_available: true,
        });
        // Restore suspended intents on reconnection
        for (const intent of this.intents.values()) {
            if (intent.principal_id === principal.principal_id &&
                intent.stateMachine.currentState === IntentState.SUSPENDED &&
                !intent.claimed_by) {
                intent.stateMachine.transition("resume");
            }
        }
        return [this.makeEnvelope(MessageType.SESSION_INFO, {
                session_id: this.sessionId,
                coordinator_principal_id: this.coordinatorId,
                created_at: this.createdAt,
                security_profile: this.securityProfile,
                compliance_profile: this.complianceProfile,
                participants: Array.from(this.participants.values()).map(p => p.principal),
            })];
    }
    handleHeartbeat(envelope) {
        const payload = envelope.payload;
        const pid = envelope.sender.principal_id;
        const info = this.participants.get(pid);
        if (info) {
            info.last_seen = Date.now();
            info.status = payload.status || "idle";
            if (!info.is_available) {
                info.is_available = true;
                for (const intent of this.intents.values()) {
                    if (intent.principal_id === pid &&
                        intent.stateMachine.currentState === IntentState.SUSPENDED &&
                        !intent.claimed_by) {
                        intent.stateMachine.transition("resume");
                    }
                }
            }
        }
        return [];
    }
    handleGoodbye(envelope) {
        const payload = envelope.payload;
        const pid = envelope.sender.principal_id;
        const disposition = payload.intent_disposition || "withdraw";
        const responses = [];
        const info = this.participants.get(pid);
        if (info) {
            info.is_available = false;
            info.status = "offline";
        }
        let activeIntentIds = payload.active_intents || [];
        if (activeIntentIds.length === 0) {
            for (const [iid, intent] of this.intents) {
                if (intent.principal_id === pid && !intent.stateMachine.isTerminal() &&
                    intent.stateMachine.currentState !== IntentState.ANNOUNCED) {
                    activeIntentIds.push(iid);
                }
            }
        }
        if (disposition === "withdraw") {
            for (const iid of activeIntentIds) {
                const intent = this.intents.get(iid);
                if (intent) {
                    try {
                        intent.stateMachine.transition("withdraw");
                        responses.push(...this.cascadeIntentTermination(iid));
                    }
                    catch { }
                }
            }
        }
        // Abandon in-flight proposals
        for (const op of this.operations.values()) {
            if (op.principal_id !== pid)
                continue;
            if (op.stateMachine.currentState === OperationState.PROPOSED) {
                op.stateMachine.transition("abandon");
            }
        }
        responses.push(...this.checkAutoDismiss());
        return responses;
    }
    // ================================================================
    //  Intent layer handlers
    // ================================================================
    handleIntentAnnounce(envelope) {
        const payload = envelope.payload;
        const intentId = payload.intent_id;
        const principalId = envelope.sender.principal_id;
        const now = Date.now();
        const intent = {
            intent_id: intentId,
            principal_id: principalId,
            objective: payload.objective,
            scope: payload.scope,
            stateMachine: new IntentStateMachine(IntentState.ANNOUNCED),
            created_at: new Date().toISOString(),
            received_at: now,
            last_message_id: envelope.message_id,
        };
        if (payload.ttl_sec !== undefined) {
            intent.ttl_sec = Number(payload.ttl_sec);
            intent.expires_at = now + intent.ttl_sec * 1000;
        }
        else if (payload.expiry_ms !== undefined) {
            intent.ttl_sec = Number(payload.expiry_ms) / 1000;
            intent.expires_at = now + Number(payload.expiry_ms);
        }
        this.intents.set(intentId, intent);
        intent.stateMachine.transition("activate");
        return this.detectScopeOverlaps(intent);
    }
    handleIntentUpdate(envelope) {
        const payload = envelope.payload;
        const intentId = payload.intent_id;
        const intent = this.intents.get(intentId);
        if (!intent || intent.principal_id !== envelope.sender.principal_id)
            return [];
        if (intent.stateMachine.currentState !== IntentState.ACTIVE)
            return [];
        let scopeChanged = false;
        if (payload.objective !== undefined)
            intent.objective = payload.objective;
        if (payload.scope !== undefined) {
            intent.scope = payload.scope;
            scopeChanged = true;
        }
        if (payload.ttl_sec !== undefined) {
            intent.ttl_sec = Number(payload.ttl_sec);
            intent.expires_at = Date.now() + intent.ttl_sec * 1000;
        }
        intent.last_message_id = envelope.message_id;
        if (scopeChanged) {
            return this.detectScopeOverlaps(intent, true);
        }
        return [];
    }
    handleIntentWithdraw(envelope) {
        const payload = envelope.payload;
        const intentId = payload.intent_id;
        const intent = this.intents.get(intentId);
        if (!intent || intent.principal_id !== envelope.sender.principal_id)
            return [];
        try {
            intent.stateMachine.transition("withdraw");
        }
        catch {
            return [];
        }
        return [...this.cascadeIntentTermination(intentId), ...this.checkAutoDismiss()];
    }
    handleIntentClaim(envelope) {
        const payload = envelope.payload;
        const originalIntentId = payload.original_intent_id;
        const newIntentId = payload.new_intent_id;
        const claimerId = envelope.sender.principal_id;
        if (!this.intents.has(originalIntentId)) {
            return [this.makeEnvelope(MessageType.PROTOCOL_ERROR, {
                    error_code: "INVALID_REFERENCE",
                    refers_to: envelope.message_id,
                    description: `Intent ${originalIntentId} does not exist`,
                })];
        }
        if (this.claims.has(originalIntentId)) {
            return [this.makeEnvelope(MessageType.PROTOCOL_ERROR, {
                    error_code: "CLAIM_CONFLICT",
                    refers_to: envelope.message_id,
                    description: `Intent ${originalIntentId} already claimed`,
                })];
        }
        const original = this.intents.get(originalIntentId);
        if (original.stateMachine.currentState !== IntentState.SUSPENDED) {
            return [this.makeEnvelope(MessageType.PROTOCOL_ERROR, {
                    error_code: "INVALID_REFERENCE",
                    refers_to: envelope.message_id,
                    description: `Intent ${originalIntentId} is not SUSPENDED`,
                })];
        }
        this.claims.set(originalIntentId, payload.claim_id);
        original.claimed_by = claimerId;
        try {
            original.stateMachine.transition("withdraw");
        }
        catch { }
        const now = Date.now();
        const newIntent = {
            intent_id: newIntentId,
            principal_id: claimerId,
            objective: payload.objective,
            scope: payload.scope,
            stateMachine: new IntentStateMachine(IntentState.ANNOUNCED),
            created_at: new Date().toISOString(),
            received_at: now,
            last_message_id: envelope.message_id,
        };
        this.intents.set(newIntentId, newIntent);
        newIntent.stateMachine.transition("activate");
        const responses = this.cascadeIntentTermination(originalIntentId);
        responses.push(...this.detectScopeOverlaps(newIntent));
        return responses;
    }
    // ================================================================
    //  Operation layer handlers
    // ================================================================
    handleOpPropose(envelope) {
        const payload = envelope.payload;
        const opId = payload.op_id;
        const intentId = payload.intent_id;
        const operation = {
            op_id: opId,
            intent_id: intentId,
            principal_id: envelope.sender.principal_id,
            target: payload.target,
            op_kind: payload.op_kind,
            stateMachine: new OperationStateMachine(OperationState.PROPOSED),
            created_at: new Date().toISOString(),
        };
        this.operations.set(opId, operation);
        for (const conflict of this.conflicts.values()) {
            if (intentId === conflict.intent_a || intentId === conflict.intent_b) {
                if (!conflict.related_ops.includes(opId))
                    conflict.related_ops.push(opId);
            }
        }
        const intent = this.intents.get(intentId);
        if (intent) {
            if (intent.stateMachine.isTerminal()) {
                operation.stateMachine.transition("reject");
                return [this.makeOpReject(opId, "intent_terminated", intent.last_message_id)];
            }
            else if (intent.stateMachine.currentState === IntentState.SUSPENDED) {
                operation.stateMachine.transition("freeze");
            }
        }
        return [];
    }
    handleOpCommit(envelope) {
        const payload = envelope.payload;
        const opId = payload.op_id;
        const intentId = payload.intent_id;
        const operation = this.operations.get(opId);
        if (operation) {
            operation.stateMachine.transition("commit");
        }
        else {
            const newOp = {
                op_id: opId, intent_id: intentId || "",
                principal_id: envelope.sender.principal_id,
                target: payload.target || "", op_kind: payload.op_kind || "",
                stateMachine: new OperationStateMachine(OperationState.PROPOSED),
                created_at: new Date().toISOString(),
            };
            newOp.stateMachine.transition("commit");
            this.operations.set(opId, newOp);
            if (intentId) {
                for (const conflict of this.conflicts.values()) {
                    if (intentId === conflict.intent_a || intentId === conflict.intent_b) {
                        if (!conflict.related_ops.includes(opId))
                            conflict.related_ops.push(opId);
                    }
                }
            }
        }
        return [];
    }
    // ================================================================
    //  Conflict layer handlers
    // ================================================================
    handleConflictReport(envelope) {
        const payload = envelope.payload;
        const conflictId = payload.conflict_id;
        if (!this.conflicts.has(conflictId)) {
            this.conflicts.set(conflictId, {
                conflict_id: conflictId, category: payload.category, severity: payload.severity,
                involved_principals: payload.involved_principals || [],
                scope_a: payload.scope_a, scope_b: payload.scope_b,
                intent_a: payload.intent_a || "", intent_b: payload.intent_b || "",
                stateMachine: new ConflictStateMachine(ConflictState.OPEN),
                created_at: Date.now(),
                related_intents: [payload.intent_a, payload.intent_b].filter(Boolean),
                related_ops: [],
            });
        }
        return [];
    }
    handleConflictAck(envelope) {
        const payload = envelope.payload;
        const conflict = this.conflicts.get(payload.conflict_id);
        if (conflict && conflict.stateMachine.currentState === ConflictState.OPEN) {
            conflict.stateMachine.transition("ack");
        }
        return [];
    }
    handleConflictEscalate(envelope) {
        const payload = envelope.payload;
        const conflict = this.conflicts.get(payload.conflict_id);
        if (!conflict)
            return [];
        try {
            if (conflict.stateMachine.currentState === ConflictState.OPEN)
                conflict.stateMachine.transition("ack");
            if (conflict.stateMachine.currentState === ConflictState.ACKED)
                conflict.stateMachine.transition("escalate");
        }
        catch {
            return [];
        }
        conflict.escalated_to = payload.escalate_to;
        conflict.escalated_at = Date.now();
        return [];
    }
    handleResolution(envelope) {
        const payload = envelope.payload;
        const conflict = this.conflicts.get(payload.conflict_id);
        if (!conflict || conflict.stateMachine.isTerminal())
            return [];
        const decision = payload.decision;
        if (decision === "dismissed") {
            conflict.stateMachine.transition("dismiss");
        }
        else {
            const st = conflict.stateMachine.currentState;
            if (st === ConflictState.OPEN) {
                conflict.stateMachine.transition("ack");
                conflict.stateMachine.transition("resolve");
                conflict.stateMachine.transition("close");
            }
            else if (st === ConflictState.ACKED) {
                conflict.stateMachine.transition("resolve");
                conflict.stateMachine.transition("close");
            }
            else if (st === ConflictState.ESCALATED) {
                conflict.stateMachine.transition("resolve");
                conflict.stateMachine.transition("close");
            }
        }
        return [];
    }
    // ================================================================
    //  Cascade & Auto-dismiss
    // ================================================================
    cascadeIntentTermination(intentId) {
        const intent = this.intents.get(intentId);
        if (!intent)
            return [];
        const responses = [];
        for (const op of this.operations.values()) {
            if (op.intent_id !== intentId)
                continue;
            if (op.stateMachine.currentState === OperationState.PROPOSED) {
                op.stateMachine.transition("reject");
                responses.push(this.makeOpReject(op.op_id, "intent_terminated", intent.last_message_id));
            }
            else if (op.stateMachine.currentState === OperationState.FROZEN) {
                op.stateMachine.transition("reject");
                responses.push(this.makeOpReject(op.op_id, "intent_terminated", intent.last_message_id));
            }
        }
        return responses;
    }
    checkAutoDismiss() {
        const responses = [];
        for (const conflict of this.conflicts.values()) {
            if (conflict.stateMachine.isTerminal())
                continue;
            const allIT = conflict.related_intents.every(iid => {
                const i = this.intents.get(iid);
                return !i || i.stateMachine.isTerminal();
            });
            if (!allIT)
                continue;
            let ok = true, hasCommitted = false;
            for (const oid of conflict.related_ops) {
                const op = this.operations.get(oid);
                if (!op)
                    continue;
                if (op.stateMachine.currentState === OperationState.COMMITTED) {
                    hasCommitted = true;
                    break;
                }
                if (!op.stateMachine.isTerminal()) {
                    ok = false;
                    break;
                }
            }
            if (hasCommitted || !ok)
                continue;
            try {
                conflict.stateMachine.transition("dismiss");
            }
            catch {
                continue;
            }
            responses.push(this.makeEnvelope(MessageType.RESOLUTION, {
                conflict_id: conflict.conflict_id, decision: "dismissed",
                rationale: "all_related_entities_terminated",
            }));
        }
        return responses;
    }
    // ================================================================
    //  Liveness cascade
    // ================================================================
    handleParticipantUnavailable(principalId) {
        const responses = [];
        responses.push(this.makeEnvelope(MessageType.PROTOCOL_ERROR, {
            error_code: "PARTICIPANT_UNAVAILABLE",
            refers_to: principalId,
            description: `Participant ${principalId} is unavailable`,
        }));
        // Suspend intents
        for (const intent of this.intents.values()) {
            if (intent.principal_id === principalId && intent.stateMachine.currentState === IntentState.ACTIVE) {
                intent.stateMachine.transition("suspend");
                for (const op of this.operations.values()) {
                    if (op.intent_id === intent.intent_id && op.stateMachine.currentState === OperationState.PROPOSED) {
                        op.stateMachine.transition("freeze");
                    }
                }
            }
        }
        // Abandon orphaned proposals
        for (const op of this.operations.values()) {
            if (op.principal_id !== principalId)
                continue;
            if (op.stateMachine.currentState === OperationState.PROPOSED) {
                op.stateMachine.transition("abandon");
            }
            else if (op.stateMachine.currentState === OperationState.FROZEN) {
                op.stateMachine.transition("abandon");
            }
        }
        return responses;
    }
    // ================================================================
    //  Helpers
    // ================================================================
    makeEnvelope(messageType, payload) {
        return createEnvelope(messageType, this.sessionId, { principal_id: this.coordinatorId, principal_type: "coordinator" }, payload, this.lamportClock.createWatermark());
    }
    makeOpReject(opId, reason, refersTo) {
        const payload = { op_id: opId, reason };
        if (refersTo)
            payload.refers_to = refersTo;
        return this.makeEnvelope(MessageType.OP_REJECT, payload);
    }
    detectScopeOverlaps(intent, skipExistingConflicts = false) {
        const responses = [];
        for (const existing of this.intents.values()) {
            if (existing.intent_id === intent.intent_id)
                continue;
            if (existing.stateMachine.currentState !== IntentState.ACTIVE &&
                existing.stateMachine.currentState !== IntentState.SUSPENDED)
                continue;
            if (!scopeOverlap(intent.scope, existing.scope))
                continue;
            if (skipExistingConflicts) {
                let alreadyExists = false;
                for (const c of this.conflicts.values()) {
                    if (c.stateMachine.isTerminal())
                        continue;
                    if ((c.intent_a === intent.intent_id && c.intent_b === existing.intent_id) ||
                        (c.intent_b === intent.intent_id && c.intent_a === existing.intent_id)) {
                        alreadyExists = true;
                        break;
                    }
                }
                if (alreadyExists)
                    continue;
            }
            const conflictId = "conflict-" + uuidv4();
            this.conflicts.set(conflictId, {
                conflict_id: conflictId, category: ConflictCategory.SCOPE_OVERLAP, severity: Severity.MEDIUM,
                involved_principals: [intent.principal_id, existing.principal_id],
                scope_a: intent.scope, scope_b: existing.scope,
                intent_a: intent.intent_id, intent_b: existing.intent_id,
                stateMachine: new ConflictStateMachine(ConflictState.OPEN),
                created_at: Date.now(),
                related_intents: [intent.intent_id, existing.intent_id], related_ops: [],
            });
            responses.push(this.makeEnvelope(MessageType.CONFLICT_REPORT, {
                conflict_id: conflictId, category: ConflictCategory.SCOPE_OVERLAP, severity: Severity.MEDIUM,
                involved_principals: [intent.principal_id, existing.principal_id],
                scope_a: intent.scope, scope_b: existing.scope,
                intent_a: intent.intent_id, intent_b: existing.intent_id,
            }));
        }
        return responses;
    }
    findArbiter() {
        for (const [pid, info] of this.participants) {
            if (!info.is_available)
                continue;
            if (info.principal.roles?.includes("arbiter"))
                return pid;
        }
        return undefined;
    }
    // Accessors for testing
    getParticipant(id) { return this.participants.get(id); }
    getIntent(id) { return this.intents.get(id); }
    getOperation(id) { return this.operations.get(id); }
    getConflict(id) { return this.conflicts.get(id); }
    getParticipants() { return Array.from(this.participants.values()); }
    getIntents() { return Array.from(this.intents.values()); }
    getOperations() { return Array.from(this.operations.values()); }
    getConflicts() { return Array.from(this.conflicts.values()); }
}
//# sourceMappingURL=coordinator.js.map