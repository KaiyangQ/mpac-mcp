import { Role, Scope } from "./models.js";
import { MessageEnvelope } from "./envelope.js";
export declare class Participant {
    private principalId;
    private principalType;
    private displayName;
    private roles;
    private capabilities;
    private lamportClock;
    constructor(principalId: string, principalType: string, displayName: string, roles?: Role[], capabilities?: string[]);
    /**
     * Send HELLO message to join session
     */
    hello(sessionId: string): MessageEnvelope;
    /**
     * Announce intent
     */
    announceIntent(sessionId: string, intentId: string, objective: string, scope: Scope, expiryMs?: number): MessageEnvelope;
    /**
     * Propose operation
     */
    proposeOp(sessionId: string, opId: string, intentId: string, target: string, opKind: string): MessageEnvelope;
    /**
     * Commit operation
     */
    commitOp(sessionId: string, opId: string, intentId: string, target: string, opKind: string, stateRefBefore?: string, stateRefAfter?: string): MessageEnvelope;
    /**
     * Report conflict
     */
    reportConflict(sessionId: string, conflictId: string, category: string, severity: string, involvedPrincipals: string[], scopeA: Scope, scopeB: Scope, details?: string): MessageEnvelope;
    /**
     * Process received message and update Lamport clock
     */
    processMessage(envelope: MessageEnvelope): void;
    /**
     * Get current Lamport clock value
     */
    getClockValue(): number;
    /**
     * Get participant info
     */
    getInfo(): {
        principal_id: string;
        principal_type: string;
        display_name: string;
        roles: Role[];
        capabilities: string[];
    };
}
//# sourceMappingURL=participant.d.ts.map