import { v4 as uuidv4 } from "uuid";
import { MessageType, Role, Scope, Sender } from "./models.js";
import { MessageEnvelope, createEnvelope } from "./envelope.js";
import { LamportClock } from "./watermark.js";

export class Participant {
  private principalId: string;
  private principalType: string;
  private displayName: string;
  private roles: Role[];
  private capabilities: string[];
  private lamportClock: LamportClock;

  constructor(
    principalId: string,
    principalType: string,
    displayName: string,
    roles: Role[] = [],
    capabilities: string[] = []
  ) {
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
  hello(sessionId: string): MessageEnvelope {
    const sender: Sender = {
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
  announceIntent(
    sessionId: string,
    intentId: string,
    objective: string,
    scope: Scope,
    expiryMs?: number
  ): MessageEnvelope {
    const sender: Sender = {
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

    return createEnvelope(
      MessageType.INTENT_ANNOUNCE,
      sessionId,
      sender,
      payload,
      watermark
    );
  }

  /**
   * Propose operation
   */
  proposeOp(
    sessionId: string,
    opId: string,
    intentId: string,
    target: string,
    opKind: string
  ): MessageEnvelope {
    const sender: Sender = {
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

    return createEnvelope(
      MessageType.OP_PROPOSE,
      sessionId,
      sender,
      payload,
      watermark
    );
  }

  /**
   * Commit operation
   */
  commitOp(
    sessionId: string,
    opId: string,
    intentId: string,
    target: string,
    opKind: string,
    stateRefBefore?: string,
    stateRefAfter?: string
  ): MessageEnvelope {
    const sender: Sender = {
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

    return createEnvelope(
      MessageType.OP_COMMIT,
      sessionId,
      sender,
      payload,
      watermark
    );
  }

  /**
   * Report conflict
   */
  reportConflict(
    sessionId: string,
    conflictId: string,
    category: string,
    severity: string,
    involvedPrincipals: string[],
    scopeA: Scope,
    scopeB: Scope,
    details?: string
  ): MessageEnvelope {
    const sender: Sender = {
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

    return createEnvelope(
      MessageType.CONFLICT_REPORT,
      sessionId,
      sender,
      payload,
      watermark
    );
  }

  /**
   * Process received message and update Lamport clock
   */
  processMessage(envelope: MessageEnvelope): void {
    if (envelope.watermark) {
      this.lamportClock.processWatermark(envelope.watermark);
    }
  }

  /**
   * Get current Lamport clock value
   */
  getClockValue(): number {
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
