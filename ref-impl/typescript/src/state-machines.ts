import {
  IntentState,
  OperationState,
  ConflictState,
  Decision,
} from "./models.js";

/**
 * Intent State Machine
 * Transitions:
 * ANNOUNCED -> ACTIVE (auto or explicit)
 * ACTIVE -> EXPIRED (timeout) | WITHDRAWN (user) | SUPERSEDED (replaced) | SUSPENDED (paused)
 * EXPIRED/WITHDRAWN/SUPERSEDED/SUSPENDED -> terminal states
 */
export class IntentStateMachine {
  private state: IntentState = IntentState.ANNOUNCED;

  constructor(initialState: IntentState = IntentState.ANNOUNCED) {
    this.state = initialState;
  }

  get currentState(): IntentState {
    return this.state;
  }

  transition(event: string): IntentState {
    const validTransitions: Record<IntentState, string[]> = {
      [IntentState.ANNOUNCED]: ["activate"],
      [IntentState.ACTIVE]: ["expire", "withdraw", "supersede", "suspend"],
      [IntentState.EXPIRED]: [],
      [IntentState.WITHDRAWN]: [],
      [IntentState.SUPERSEDED]: [],
      [IntentState.SUSPENDED]: ["resume", "expire", "withdraw"],
    };

    if (!validTransitions[this.state]?.includes(event)) {
      throw new Error(
        `Invalid transition from ${this.state} on event ${event}`
      );
    }

    switch (this.state) {
      case IntentState.ANNOUNCED:
        if (event === "activate") {
          this.state = IntentState.ACTIVE;
        }
        break;
      case IntentState.ACTIVE:
        if (event === "expire") {
          this.state = IntentState.EXPIRED;
        } else if (event === "withdraw") {
          this.state = IntentState.WITHDRAWN;
        } else if (event === "supersede") {
          this.state = IntentState.SUPERSEDED;
        } else if (event === "suspend") {
          this.state = IntentState.SUSPENDED;
        }
        break;
      case IntentState.SUSPENDED:
        if (event === "resume") {
          this.state = IntentState.ACTIVE;
        } else if (event === "expire") {
          this.state = IntentState.EXPIRED;
        } else if (event === "withdraw") {
          this.state = IntentState.WITHDRAWN;
        }
        break;
    }

    return this.state;
  }

  isTerminal(): boolean {
    return [
      IntentState.EXPIRED,
      IntentState.WITHDRAWN,
      IntentState.SUPERSEDED,
    ].includes(this.state);
  }
}

/**
 * Operation State Machine
 * Transitions:
 * PROPOSED -> COMMITTED (success) | REJECTED (error) | ABANDONED (cancelled) | FROZEN (paused)
 * COMMITTED/REJECTED/ABANDONED/FROZEN -> terminal states
 */
export class OperationStateMachine {
  private state: OperationState = OperationState.PROPOSED;

  constructor(initialState: OperationState = OperationState.PROPOSED) {
    this.state = initialState;
  }

  get currentState(): OperationState {
    return this.state;
  }

  transition(event: string): OperationState {
    const validTransitions: Record<OperationState, string[]> = {
      [OperationState.PROPOSED]: ["commit", "reject", "abandon", "freeze"],
      [OperationState.COMMITTED]: [],
      [OperationState.REJECTED]: [],
      [OperationState.ABANDONED]: [],
      [OperationState.FROZEN]: ["unfreeze", "reject", "abandon"],
    };

    if (!validTransitions[this.state]?.includes(event)) {
      throw new Error(
        `Invalid transition from ${this.state} on event ${event}`
      );
    }

    switch (this.state) {
      case OperationState.PROPOSED:
        if (event === "commit") {
          this.state = OperationState.COMMITTED;
        } else if (event === "reject") {
          this.state = OperationState.REJECTED;
        } else if (event === "abandon") {
          this.state = OperationState.ABANDONED;
        } else if (event === "freeze") {
          this.state = OperationState.FROZEN;
        }
        break;
      case OperationState.FROZEN:
        if (event === "unfreeze") {
          this.state = OperationState.PROPOSED;
        } else if (event === "reject") {
          this.state = OperationState.REJECTED;
        } else if (event === "abandon") {
          this.state = OperationState.ABANDONED;
        }
        break;
    }

    return this.state;
  }

  isTerminal(): boolean {
    return [
      OperationState.COMMITTED,
      OperationState.REJECTED,
      OperationState.ABANDONED,
    ].includes(this.state);
  }
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
export class ConflictStateMachine {
  private state: ConflictState = ConflictState.OPEN;

  constructor(initialState: ConflictState = ConflictState.OPEN) {
    this.state = initialState;
  }

  get currentState(): ConflictState {
    return this.state;
  }

  transition(event: string): ConflictState {
    const validTransitions: Record<ConflictState, string[]> = {
      [ConflictState.OPEN]: ["ack", "escalate", "dismiss"],
      [ConflictState.ACKED]: ["escalate", "resolve", "dismiss"],
      [ConflictState.ESCALATED]: ["resolve", "dismiss"],
      [ConflictState.RESOLVED]: ["close"],
      [ConflictState.CLOSED]: [],
      [ConflictState.DISMISSED]: [],
    };

    if (!validTransitions[this.state]?.includes(event)) {
      throw new Error(
        `Invalid transition from ${this.state} on event ${event}`
      );
    }

    switch (this.state) {
      case ConflictState.OPEN:
        if (event === "ack") {
          this.state = ConflictState.ACKED;
        } else if (event === "escalate") {
          this.state = ConflictState.ESCALATED;
        } else if (event === "dismiss") {
          this.state = ConflictState.DISMISSED;
        }
        break;
      case ConflictState.ACKED:
        if (event === "escalate") {
          this.state = ConflictState.ESCALATED;
        } else if (event === "resolve") {
          this.state = ConflictState.RESOLVED;
        } else if (event === "dismiss") {
          this.state = ConflictState.DISMISSED;
        }
        break;
      case ConflictState.ESCALATED:
        if (event === "resolve") {
          this.state = ConflictState.RESOLVED;
        } else if (event === "dismiss") {
          this.state = ConflictState.DISMISSED;
        }
        break;
      case ConflictState.RESOLVED:
        if (event === "close") {
          this.state = ConflictState.CLOSED;
        }
        break;
    }

    return this.state;
  }

  isTerminal(): boolean {
    return [ConflictState.CLOSED, ConflictState.DISMISSED].includes(
      this.state
    );
  }
}
