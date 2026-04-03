import { IntentState, OperationState, ConflictState } from "./models.js";
/**
 * Intent State Machine
 * Transitions:
 * ANNOUNCED -> ACTIVE (auto or explicit)
 * ACTIVE -> EXPIRED (timeout) | WITHDRAWN (user) | SUPERSEDED (replaced) | SUSPENDED (paused)
 * EXPIRED/WITHDRAWN/SUPERSEDED/SUSPENDED -> terminal states
 */
export declare class IntentStateMachine {
    private state;
    constructor(initialState?: IntentState);
    get currentState(): IntentState;
    transition(event: string): IntentState;
    isTerminal(): boolean;
}
/**
 * Operation State Machine
 * Transitions:
 * PROPOSED -> COMMITTED (success) | REJECTED (error) | ABANDONED (cancelled) | FROZEN (paused)
 * COMMITTED/REJECTED/ABANDONED/FROZEN -> terminal states
 */
export declare class OperationStateMachine {
    private state;
    constructor(initialState?: OperationState);
    get currentState(): OperationState;
    transition(event: string): OperationState;
    isTerminal(): boolean;
}
/**
 * Conflict State Machine
 * Transitions:
 * OPEN -> ACKED (acknowledged) | ESCALATED (needs admin) | DISMISSED (auto-dismiss)
 * ACKED -> ESCALATED | RESOLVED | DISMISSED
 * ESCALATED -> RESOLVED | DISMISSED
 * RESOLVED -> CLOSED
 * CLOSED -> terminal
 * DISMISSED -> terminal
 */
export declare class ConflictStateMachine {
    private state;
    constructor(initialState?: ConflictState);
    get currentState(): ConflictState;
    transition(event: string): ConflictState;
    isTerminal(): boolean;
}
//# sourceMappingURL=state-machines.d.ts.map