import { Scope } from "./models.js";
/**
 * Detect if two scopes overlap
 * Returns true if there is any overlap, false if no overlap, conservative true for unknown kinds
 */
export declare function scopeOverlap(a: Scope, b: Scope): boolean;
/**
 * Check if scope is valid (has at least one non-empty set)
 */
export declare function isValidScope(scope: Scope): boolean;
//# sourceMappingURL=scope.d.ts.map