import { v4 as uuidv4 } from "uuid";
import {
  MessageType,
  Principal,
  SecurityProfile,
  ComplianceProfile,
  IntentState,
  OperationState,
  ConflictState,
  ConflictCategory,
  Severity,
  Sender,
} from "./models.js";
import { MessageEnvelope, createEnvelope } from "./envelope.js";
import { LamportClock } from "./watermark.js";
import { scopeOverlap } from "./scope.js";
import {
  IntentStateMachine,
  OperationStateMachine,
  ConflictStateMachine,
} from "./state-machines.js";

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
  created_at: number; // ms timestamp
  related_intents: string[];
  related_ops: string[];
  escalated_to?: string;
  escalated_at?: number;
}

interface ParticipantInfo {
  principal: Principal;
  last_seen: number; // Date.now() ms
  status: string;
  is_available: boolean;
}

export class SessionCoordinator {
  private sessionId: string;
  private coordinatorId: string = "coordinator-" + uuidv4();
  private securityProfile: SecurityProfile;
  private complianceProfile: ComplianceProfile;
  private participants: Map<string, ParticipantInfo> = new Map();
  private intents: Map<string, Intent> = new Map();
  private operations: Map<string, Operation> = new Map();
  private conflicts: Map<string, Conflict> = new Map();
  private lamportClock: LamportClock;
  private createdAt: string;
  private intentExpiryGraceSec: number;
  private unavailabilityTimeoutMs: number;
  private resolutionTimeoutMs: number;
  private claims: Map<string, string> = new Map(); // original_intent_id → claim_id
  private sessionClosed: boolean;
  private sessionStartedAt: number;
  private auditLog: MessageEnvelope[] = [];

  constructor(
    sessionId: string,
    securityProfile: SecurityProfile = SecurityProfile.OPEN,
    complianceProfile: ComplianceProfile = ComplianceProfile.CORE,
    intentExpiryGraceSec: number = 30,
    unavailabilityTimeoutSec: number = 90,
    resolutionTimeoutSec: number = 300
  ) {
    this.sessionId = sessionId;
    this.securityProfile = securityProfile;
    this.complianceProfile = complianceProfile;
    this.lamportClock = new LamportClock();
    this.createdAt = new Date().toISOString();
    this.intentExpiryGraceSec = intentExpiryGraceSec;
    this.unavailabilityTimeoutMs = unavailabilityTimeoutSec * 1000;
    this.resolutionTimeoutMs = resolutionTimeoutSec * 1000;
    this.coordinatorId = `service:coordinator-${sessionId}`;
    this.sessionClosed = false;
    this.sessionStartedAt = Date.now();
  }

  // ================================================================
  //  Main message processing
  // ================================================================

  processMessage(envelope: MessageEnvelope): MessageEnvelope[] {
    const responses: MessageEnvelope[] = [];

    this.auditLog.push(envelope);

    if (envelope.watermark) {
      this.lamportClock.processWatermark(envelope.watermark);
    }

    // Update liveness for sender
    const pid = envelope.sender.principal_id;
    const pInfo = this.participants.get(pid);
    if (pInfo) pInfo.last_seen = Date.now();

    const mt = envelope.message_type;

    // Reject messages for closed sessions
    if (this.sessionClosed && mt !== MessageType.SESSION_CLOSE && mt !== MessageType.GOODBYE) {
      return [this.makeEnvelope(MessageType.PROTOCOL_ERROR, {
        error_code: "SESSION_CLOSED",
        refers_to: envelope.message_id,
        description: `Session ${this.sessionId} has been closed`,
      })];
    }

    switch (mt) {
      case MessageType.HELLO:
        responses.push(...this.handleHello(envelope)); break;
      case MessageType.HEARTBEAT:
        responses.push(...this.handleHeartbeat(envelope)); break;
      case MessageType.GOODBYE:
        responses.push(...this.handleGoodbye(envelope)); break;
      case MessageType.INTENT_ANNOUNCE:
        responses.push(...this.handleIntentAnnounce(envelope)); break;
      case MessageType.INTENT_UPDATE:
        responses.push(...this.handleIntentUpdate(envelope)); break;
      case MessageType.INTENT_WITHDRAW:
        responses.push(...this.handleIntentWithdraw(envelope)); break;
      case MessageType.INTENT_CLAIM:
        responses.push(...this.handleIntentClaim(envelope)); break;
      case MessageType.OP_PROPOSE:
        responses.push(...this.handleOpPropose(envelope)); break;
      case MessageType.OP_COMMIT:
        responses.push(...this.handleOpCommit(envelope)); break;
      case MessageType.OP_SUPERSEDE:
        responses.push(...this.handleOpSupersede(envelope)); break;
      case MessageType.CONFLICT_REPORT:
        responses.push(...this.handleConflictReport(envelope)); break;
      case MessageType.CONFLICT_ACK:
        responses.push(...this.handleConflictAck(envelope)); break;
      case MessageType.CONFLICT_ESCALATE:
        responses.push(...this.handleConflictEscalate(envelope)); break;
      case MessageType.RESOLUTION:
        responses.push(...this.handleResolution(envelope)); break;
      case MessageType.SESSION_CLOSE:
        // SESSION_CLOSE is coordinator-originated only
        return [];
      case MessageType.COORDINATOR_STATUS:
        // COORDINATOR_STATUS is outbound-only
        return [];
    }

    return responses;
  }

  // ================================================================
  //  Time-based lifecycle
  // ================================================================

  checkExpiry(nowMs?: number): MessageEnvelope[] {
    const now = nowMs ?? Date.now();
    const allResponses: MessageEnvelope[] = [];

    for (const intent of this.intents.values()) {
      if (
        intent.expires_at !== undefined &&
        !intent.stateMachine.isTerminal() &&
        intent.stateMachine.currentState !== IntentState.ANNOUNCED &&
        now >= intent.expires_at
      ) {
        intent.stateMachine.transition("expire");
        allResponses.push(...this.cascadeIntentTermination(intent.intent_id));
      }
    }

    allResponses.push(...this.checkAutoDismiss());
    return allResponses;
  }

  checkLiveness(nowMs?: number): MessageEnvelope[] {
    const now = nowMs ?? Date.now();
    const allResponses: MessageEnvelope[] = [];

    for (const [pid, info] of this.participants) {
      if (!info.is_available || info.status === "offline") continue;
      if (now - info.last_seen > this.unavailabilityTimeoutMs) {
        info.is_available = false;
        allResponses.push(...this.handleParticipantUnavailable(pid));
      }
    }

    return allResponses;
  }

  checkResolutionTimeouts(nowMs?: number): MessageEnvelope[] {
    const now = nowMs ?? Date.now();
    const allResponses: MessageEnvelope[] = [];

    for (const conflict of this.conflicts.values()) {
      const st = conflict.stateMachine.currentState;
      if (st !== ConflictState.OPEN && st !== ConflictState.ACKED) continue;
      if (now - conflict.created_at <= this.resolutionTimeoutMs) continue;

      const arbiterId = this.findArbiter();
      if (arbiterId) {
        try {
          if (st === ConflictState.OPEN) conflict.stateMachine.transition("ack");
          conflict.stateMachine.transition("escalate");
        } catch { continue; }
        conflict.escalated_to = arbiterId;
        conflict.escalated_at = now;
        allResponses.push(this.makeEnvelope(MessageType.CONFLICT_ESCALATE, {
          conflict_id: conflict.conflict_id,
          escalate_to: arbiterId,
          reason: "resolution_timeout",
        }));
      } else {
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

  private handleHello(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const principal: Principal = {
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
      if (
        intent.principal_id === principal.principal_id &&
        intent.stateMachine.currentState === IntentState.SUSPENDED &&
        !intent.claimed_by
      ) {
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

  private handleHeartbeat(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const pid = envelope.sender.principal_id;
    const info = this.participants.get(pid);
    if (info) {
      info.last_seen = Date.now();
      info.status = payload.status || "idle";
      if (!info.is_available) {
        info.is_available = true;
        for (const intent of this.intents.values()) {
          if (
            intent.principal_id === pid &&
            intent.stateMachine.currentState === IntentState.SUSPENDED &&
            !intent.claimed_by
          ) {
            intent.stateMachine.transition("resume");
          }
        }
      }
    }
    return [];
  }

  private handleGoodbye(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const pid = envelope.sender.principal_id;
    const disposition = payload.intent_disposition || "withdraw";
    const responses: MessageEnvelope[] = [];

    const info = this.participants.get(pid);
    if (info) { info.is_available = false; info.status = "offline"; }

    let activeIntentIds: string[] = payload.active_intents || [];
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
          } catch {}
        }
      }
    }

    // Abandon in-flight proposals
    for (const op of this.operations.values()) {
      if (op.principal_id !== pid) continue;
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

  private handleIntentAnnounce(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const intentId = payload.intent_id;
    const principalId = envelope.sender.principal_id;
    const now = Date.now();

    const intent: Intent = {
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
    } else if (payload.expiry_ms !== undefined) {
      intent.ttl_sec = Number(payload.expiry_ms) / 1000;
      intent.expires_at = now + Number(payload.expiry_ms);
    }

    this.intents.set(intentId, intent);
    intent.stateMachine.transition("activate");

    return this.detectScopeOverlaps(intent);
  }

  private handleIntentUpdate(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const intentId = payload.intent_id;
    const intent = this.intents.get(intentId);
    if (!intent || intent.principal_id !== envelope.sender.principal_id) return [];
    if (intent.stateMachine.currentState !== IntentState.ACTIVE) return [];

    let scopeChanged = false;

    if (payload.objective !== undefined) intent.objective = payload.objective;
    if (payload.scope !== undefined) { intent.scope = payload.scope; scopeChanged = true; }
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

  private handleIntentWithdraw(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const intentId = payload.intent_id;
    const intent = this.intents.get(intentId);
    if (!intent || intent.principal_id !== envelope.sender.principal_id) return [];
    try { intent.stateMachine.transition("withdraw"); } catch { return []; }
    return [...this.cascadeIntentTermination(intentId), ...this.checkAutoDismiss()];
  }

  private handleIntentClaim(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
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

    const original = this.intents.get(originalIntentId)!;
    if (original.stateMachine.currentState !== IntentState.SUSPENDED) {
      return [this.makeEnvelope(MessageType.PROTOCOL_ERROR, {
        error_code: "INVALID_REFERENCE",
        refers_to: envelope.message_id,
        description: `Intent ${originalIntentId} is not SUSPENDED`,
      })];
    }

    this.claims.set(originalIntentId, payload.claim_id);
    original.claimed_by = claimerId;
    try { original.stateMachine.transition("withdraw"); } catch {}

    const now = Date.now();
    const newIntent: Intent = {
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

  private handleOpPropose(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const opId = payload.op_id;
    const intentId = payload.intent_id;

    const operation: Operation = {
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
        if (!conflict.related_ops.includes(opId)) conflict.related_ops.push(opId);
      }
    }

    const intent = this.intents.get(intentId);
    if (intent) {
      if (intent.stateMachine.isTerminal()) {
        operation.stateMachine.transition("reject");
        return [this.makeOpReject(opId, "intent_terminated", intent.last_message_id)];
      } else if (intent.stateMachine.currentState === IntentState.SUSPENDED) {
        operation.stateMachine.transition("freeze");
      }
    }
    return [];
  }

  private handleOpCommit(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const opId = payload.op_id;
    const intentId = payload.intent_id;

    const operation = this.operations.get(opId);
    if (operation) {
      operation.stateMachine.transition("commit");
    } else {
      const newOp: Operation = {
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
            if (!conflict.related_ops.includes(opId)) conflict.related_ops.push(opId);
          }
        }
      }
    }
    return [];
  }

  private handleOpSupersede(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const opId = payload.op_id;
    const supersedesOpId = payload.supersedes_op_id;
    const intentId = payload.intent_id;
    const target = payload.target;

    // Validate superseded op exists and is COMMITTED
    const oldOp = this.operations.get(supersedesOpId);
    if (!oldOp) {
      return [this.makeEnvelope(MessageType.PROTOCOL_ERROR, {
        error_code: "INVALID_REFERENCE",
        refers_to: envelope.message_id,
        description: `Operation ${supersedesOpId} does not exist`,
      })];
    }

    if (oldOp.stateMachine.currentState !== OperationState.COMMITTED) {
      return [this.makeEnvelope(MessageType.PROTOCOL_ERROR, {
        error_code: "INVALID_REFERENCE",
        refers_to: envelope.message_id,
        description: `Operation ${supersedesOpId} is not COMMITTED (state: ${oldOp.stateMachine.currentState})`,
      })];
    }

    // Transition old op to SUPERSEDED
    oldOp.stateMachine.transition("supersede");

    // Create new op as COMMITTED
    const newOp: Operation = {
      op_id: opId,
      intent_id: intentId || oldOp.intent_id,
      principal_id: envelope.sender.principal_id,
      target: target || oldOp.target,
      op_kind: payload.op_kind || oldOp.op_kind,
      stateMachine: new OperationStateMachine(OperationState.PROPOSED),
      created_at: new Date().toISOString(),
    };
    newOp.stateMachine.transition("commit");
    this.operations.set(opId, newOp);

    // Track in related conflicts
    const effectiveIntentId = intentId || oldOp.intent_id;
    if (effectiveIntentId) {
      for (const conflict of this.conflicts.values()) {
        if (effectiveIntentId === conflict.intent_a || effectiveIntentId === conflict.intent_b) {
          if (!conflict.related_ops.includes(opId)) conflict.related_ops.push(opId);
        }
      }
    }

    return [];
  }

  // ================================================================
  //  Conflict layer handlers
  // ================================================================

  private handleConflictReport(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
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

  private handleConflictAck(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const conflict = this.conflicts.get(payload.conflict_id);
    if (conflict && conflict.stateMachine.currentState === ConflictState.OPEN) {
      conflict.stateMachine.transition("ack");
    }
    return [];
  }

  private handleConflictEscalate(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const conflict = this.conflicts.get(payload.conflict_id);
    if (!conflict) return [];
    try {
      if (conflict.stateMachine.currentState === ConflictState.OPEN) conflict.stateMachine.transition("ack");
      if (conflict.stateMachine.currentState === ConflictState.ACKED) conflict.stateMachine.transition("escalate");
    } catch { return []; }
    conflict.escalated_to = payload.escalate_to;
    conflict.escalated_at = Date.now();
    return [];
  }

  private handleResolution(envelope: MessageEnvelope): MessageEnvelope[] {
    const payload = envelope.payload as any;
    const conflict = this.conflicts.get(payload.conflict_id);
    if (!conflict || conflict.stateMachine.isTerminal()) return [];
    const decision = payload.decision;

    if (decision === "dismissed") {
      conflict.stateMachine.transition("dismiss");
    } else {
      const st = conflict.stateMachine.currentState;
      if (st === ConflictState.OPEN) {
        conflict.stateMachine.transition("ack");
        conflict.stateMachine.transition("resolve");
        conflict.stateMachine.transition("close");
      } else if (st === ConflictState.ACKED) {
        conflict.stateMachine.transition("resolve");
        conflict.stateMachine.transition("close");
      } else if (st === ConflictState.ESCALATED) {
        conflict.stateMachine.transition("resolve");
        conflict.stateMachine.transition("close");
      }
    }
    return [];
  }

  // ================================================================
  //  Cascade & Auto-dismiss
  // ================================================================

  private cascadeIntentTermination(intentId: string): MessageEnvelope[] {
    const intent = this.intents.get(intentId);
    if (!intent) return [];
    const responses: MessageEnvelope[] = [];
    for (const op of this.operations.values()) {
      if (op.intent_id !== intentId) continue;
      if (op.stateMachine.currentState === OperationState.PROPOSED) {
        op.stateMachine.transition("reject");
        responses.push(this.makeOpReject(op.op_id, "intent_terminated", intent.last_message_id));
      } else if (op.stateMachine.currentState === OperationState.FROZEN) {
        op.stateMachine.transition("reject");
        responses.push(this.makeOpReject(op.op_id, "intent_terminated", intent.last_message_id));
      }
    }
    return responses;
  }

  private checkAutoDismiss(): MessageEnvelope[] {
    const responses: MessageEnvelope[] = [];
    for (const conflict of this.conflicts.values()) {
      if (conflict.stateMachine.isTerminal()) continue;
      const allIT = conflict.related_intents.every(iid => {
        const i = this.intents.get(iid); return !i || i.stateMachine.isTerminal();
      });
      if (!allIT) continue;
      let ok = true, hasCommitted = false;
      for (const oid of conflict.related_ops) {
        const op = this.operations.get(oid); if (!op) continue;
        if (op.stateMachine.currentState === OperationState.COMMITTED) { hasCommitted = true; break; }
        if (!op.stateMachine.isTerminal()) { ok = false; break; }
      }
      if (hasCommitted || !ok) continue;
      try { conflict.stateMachine.transition("dismiss"); } catch { continue; }
      responses.push(this.makeEnvelope(MessageType.RESOLUTION, {
        conflict_id: conflict.conflict_id, decision: "dismissed",
        rationale: "all_related_entities_terminated",
      }));
    }
    return responses;
  }

  // ================================================================
  //  Fault Recovery (Section 8.1.1)
  // ================================================================

  recoverFromSnapshot(snapshotData: any): void {
    this.lamportClock = new LamportClock();
    (this.lamportClock as any).clock = snapshotData.lamport_clock || 0;
    this.sessionClosed = snapshotData.session_closed || false;

    // Restore participants
    this.participants.clear();
    for (const p of snapshotData.participants || []) {
      this.participants.set(p.principal_id, {
        principal: {
          principal_id: p.principal_id,
          principal_type: "agent",
          display_name: p.display_name,
          roles: p.roles,
        },
        last_seen: p.last_seen ? new Date(p.last_seen).getTime() : Date.now(),
        status: p.status || "idle",
        is_available: p.is_available ?? true,
      });
    }

    // Restore intents
    this.intents.clear();
    for (const i of snapshotData.intents || []) {
      const sm = new IntentStateMachine(IntentState.ANNOUNCED);
      const st = i.state;
      if (st === "ACTIVE" || st === IntentState.ACTIVE) sm.transition("activate");
      else if (st === "EXPIRED" || st === IntentState.EXPIRED) { sm.transition("activate"); sm.transition("expire"); }
      else if (st === "WITHDRAWN" || st === IntentState.WITHDRAWN) { sm.transition("activate"); sm.transition("withdraw"); }
      else if (st === "SUPERSEDED" || st === IntentState.SUPERSEDED) { sm.transition("activate"); sm.transition("supersede"); }
      else if (st === "SUSPENDED" || st === IntentState.SUSPENDED) { sm.transition("activate"); sm.transition("suspend"); }

      this.intents.set(i.intent_id, {
        intent_id: i.intent_id,
        principal_id: i.principal_id || "",
        objective: i.objective || "",
        scope: i.scope || { kind: "file_set" },
        stateMachine: sm,
        created_at: new Date().toISOString(),
        received_at: Date.now(),
        expires_at: i.expires_at ? new Date(i.expires_at).getTime() : undefined,
      });
    }

    // Restore operations
    this.operations.clear();
    for (const o of snapshotData.operations || []) {
      const sm = new OperationStateMachine(OperationState.PROPOSED);
      const st = o.state;
      if (st === "COMMITTED" || st === OperationState.COMMITTED) sm.transition("commit");
      else if (st === "REJECTED" || st === OperationState.REJECTED) sm.transition("reject");
      else if (st === "ABANDONED" || st === OperationState.ABANDONED) sm.transition("abandon");
      else if (st === "FROZEN" || st === OperationState.FROZEN) sm.transition("freeze");
      else if (st === "SUPERSEDED" || st === OperationState.SUPERSEDED) { sm.transition("commit"); sm.transition("supersede"); }

      this.operations.set(o.op_id, {
        op_id: o.op_id,
        intent_id: o.intent_id || "",
        principal_id: o.principal_id || "",
        target: o.target || "",
        op_kind: o.op_kind || "",
        stateMachine: sm,
        created_at: new Date().toISOString(),
      });
    }

    // Restore conflicts
    this.conflicts.clear();
    for (const c of snapshotData.conflicts || []) {
      const sm = new ConflictStateMachine(ConflictState.OPEN);
      const st = c.state;
      if (st === "ACKED" || st === ConflictState.ACKED) sm.transition("ack");
      else if (st === "ESCALATED" || st === ConflictState.ESCALATED) { sm.transition("ack"); sm.transition("escalate"); }
      else if (st === "RESOLVED" || st === ConflictState.RESOLVED) { sm.transition("ack"); sm.transition("resolve"); }
      else if (st === "CLOSED" || st === ConflictState.CLOSED) { sm.transition("ack"); sm.transition("resolve"); sm.transition("close"); }
      else if (st === "DISMISSED" || st === ConflictState.DISMISSED) sm.transition("dismiss");

      this.conflicts.set(c.conflict_id, {
        conflict_id: c.conflict_id,
        category: c.category || "scope_overlap",
        severity: c.severity || "medium",
        involved_principals: c.involved_principals || [],
        scope_a: c.scope_a,
        scope_b: c.scope_b,
        intent_a: c.intent_a || "",
        intent_b: c.intent_b || "",
        stateMachine: sm,
        created_at: c.created_at || Date.now(),
        related_intents: c.related_intents || [],
        related_ops: c.related_ops || [],
      });
    }
  }

  replayAuditLog(messages: MessageEnvelope[]): MessageEnvelope[] {
    const allResponses: MessageEnvelope[] = [];
    for (const msg of messages) {
      allResponses.push(...this.processMessage(msg));
    }
    return allResponses;
  }

  getAuditLog(): MessageEnvelope[] {
    return [...this.auditLog];
  }

  // ================================================================
  //  Liveness cascade
  // ================================================================

  private handleParticipantUnavailable(principalId: string): MessageEnvelope[] {
    const responses: MessageEnvelope[] = [];

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
      if (op.principal_id !== principalId) continue;
      if (op.stateMachine.currentState === OperationState.PROPOSED) {
        op.stateMachine.transition("abandon");
      } else if (op.stateMachine.currentState === OperationState.FROZEN) {
        op.stateMachine.transition("abandon");
      }
    }

    return responses;
  }

  // ================================================================
  //  Helpers
  // ================================================================

  private makeEnvelope(messageType: MessageType | string, payload: any): MessageEnvelope {
    return createEnvelope(
      messageType as MessageType, this.sessionId,
      { principal_id: this.coordinatorId, principal_type: "coordinator" },
      payload, this.lamportClock.createWatermark()
    );
  }

  private makeOpReject(opId: string, reason: string, refersTo?: string): MessageEnvelope {
    const payload: any = { op_id: opId, reason };
    if (refersTo) payload.refers_to = refersTo;
    return this.makeEnvelope(MessageType.OP_REJECT, payload);
  }

  private detectScopeOverlaps(intent: Intent, skipExistingConflicts = false): MessageEnvelope[] {
    const responses: MessageEnvelope[] = [];
    for (const existing of this.intents.values()) {
      if (existing.intent_id === intent.intent_id) continue;
      if (existing.stateMachine.currentState !== IntentState.ACTIVE &&
          existing.stateMachine.currentState !== IntentState.SUSPENDED) continue;
      if (!scopeOverlap(intent.scope, existing.scope)) continue;

      if (skipExistingConflicts) {
        let alreadyExists = false;
        for (const c of this.conflicts.values()) {
          if (c.stateMachine.isTerminal()) continue;
          if ((c.intent_a === intent.intent_id && c.intent_b === existing.intent_id) ||
              (c.intent_b === intent.intent_id && c.intent_a === existing.intent_id)) {
            alreadyExists = true; break;
          }
        }
        if (alreadyExists) continue;
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

  private findArbiter(): string | undefined {
    for (const [pid, info] of this.participants) {
      if (!info.is_available) continue;
      if (info.principal.roles?.includes("arbiter" as any)) return pid;
    }
    return undefined;
  }

  // ================================================================
  //  Session lifecycle (v0.1.5)
  // ================================================================

  closeSession(reason = "manual"): MessageEnvelope[] {
    if (this.sessionClosed) return [];
    this.sessionClosed = true;

    // Withdraw all active intents
    for (const intent of this.intents.values()) {
      if (!intent.stateMachine.isTerminal() && intent.stateMachine.currentState !== IntentState.ANNOUNCED) {
        try { intent.stateMachine.transition("withdraw"); } catch {}
      }
    }

    // Abandon all in-flight operations
    for (const op of this.operations.values()) {
      if (op.stateMachine.currentState === OperationState.PROPOSED || op.stateMachine.currentState === OperationState.FROZEN) {
        try { op.stateMachine.transition("abandon"); } catch {}
      }
    }

    const summary = this.buildSessionSummary();
    return [this.makeEnvelope(MessageType.SESSION_CLOSE, {
      reason,
      final_lamport_clock: this.lamportClock.value,
      summary,
      active_intents_disposition: "withdraw_all",
    })];
  }

  checkAutoClose(): MessageEnvelope[] {
    if (this.sessionClosed) return [];

    for (const intent of this.intents.values()) {
      if (!intent.stateMachine.isTerminal()) return [];
    }
    for (const op of this.operations.values()) {
      if (op.stateMachine.currentState === OperationState.PROPOSED || op.stateMachine.currentState === OperationState.FROZEN) return [];
    }
    for (const conflict of this.conflicts.values()) {
      if (conflict.stateMachine.currentState !== ConflictState.CLOSED && conflict.stateMachine.currentState !== ConflictState.DISMISSED) return [];
    }
    if (this.intents.size === 0) return [];

    return this.closeSession("completed");
  }

  coordinatorStatus(event = "heartbeat"): MessageEnvelope[] {
    let openConflicts = 0;
    for (const c of this.conflicts.values()) {
      if (c.stateMachine.currentState !== ConflictState.CLOSED && c.stateMachine.currentState !== ConflictState.DISMISSED) openConflicts++;
    }
    let activeParticipants = 0;
    for (const p of this.participants.values()) {
      if (p.is_available) activeParticipants++;
    }

    return [this.makeEnvelope(MessageType.COORDINATOR_STATUS, {
      event,
      coordinator_id: this.coordinatorId,
      session_health: openConflicts === 0 ? "healthy" : "degraded",
      active_participants: activeParticipants,
      open_conflicts: openConflicts,
      snapshot_lamport_clock: this.lamportClock.value,
    })];
  }

  snapshot(): any {
    const participants = [];
    for (const [pid, info] of this.participants.entries()) {
      participants.push({
        principal_id: pid,
        display_name: info.principal.display_name,
        roles: info.principal.roles,
        status: info.status,
        is_available: info.is_available,
        last_seen: new Date(info.last_seen).toISOString(),
      });
    }
    const intents = [];
    for (const intent of this.intents.values()) {
      intents.push({
        intent_id: intent.intent_id,
        principal_id: intent.principal_id,
        state: intent.stateMachine.currentState,
        scope: intent.scope,
        expires_at: intent.expires_at ? new Date(intent.expires_at).toISOString() : null,
      });
    }
    const operations = [];
    for (const op of this.operations.values()) {
      operations.push({
        op_id: op.op_id,
        intent_id: op.intent_id,
        state: op.stateMachine.currentState,
        target: op.target,
      });
    }
    const conflicts = [];
    for (const c of this.conflicts.values()) {
      conflicts.push({
        conflict_id: c.conflict_id,
        state: c.stateMachine.currentState,
        related_intents: c.related_intents || [c.intent_a, c.intent_b],
        related_ops: c.related_ops || [],
      });
    }

    return {
      snapshot_version: 1,
      session_id: this.sessionId,
      protocol_version: "0.1.6",
      captured_at: new Date().toISOString(),
      lamport_clock: this.lamportClock.value,
      participants,
      intents,
      operations,
      conflicts,
      session_closed: this.sessionClosed,
    };
  }

  private buildSessionSummary(): any {
    const nowMs = Date.now();
    const durationSec = Math.floor((nowMs - this.sessionStartedAt) / 1000);
    return {
      total_intents: this.intents.size,
      total_operations: this.operations.size,
      total_conflicts: this.conflicts.size,
      total_participants: this.participants.size,
      duration_sec: durationSec,
    };
  }

  // Accessors for testing
  getParticipant(id: string) { return this.participants.get(id); }
  getIntent(id: string) { return this.intents.get(id); }
  getOperation(id: string) { return this.operations.get(id); }
  getConflict(id: string) { return this.conflicts.get(id); }
  getParticipants() { return Array.from(this.participants.values()); }
  getIntents() { return Array.from(this.intents.values()); }
  getOperations() { return Array.from(this.operations.values()); }
  getConflicts() { return Array.from(this.conflicts.values()); }
}
