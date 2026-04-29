// Minimal MPAC envelope types — just enough for the frontend to parse
// messages coming from the coordinator. Mirrors the wire format defined in
// `mpac-package/src/mpac_protocol/core/envelope.py` but we only type the
// fields our UI actually reads.

export type Sender = {
  principal_id: string;
  principal_type: "human" | "agent" | "coordinator" | string;
  sender_instance_id: string;
};

export type MpacEnvelope<TPayload = Record<string, unknown>> = {
  protocol: "MPAC";
  version: string;
  message_type: string;
  message_id: string;
  session_id: string;
  sender: Sender;
  ts: string;
  payload: TPayload;
};

// Payloads we care about (loose typing — extra fields ignored).

export type SessionInfoPayload = {
  session_id?: string;
  participants?: Array<{
    principal_id: string;
    principal_type?: string;
    display_name?: string;
    roles?: string[];
    status?: string;
    active_intent_id?: string | null;
    last_seen?: string;
    identity_verified?: boolean;
  }>;
  security_profile?: string;
  granted_roles?: string[];
};

export type ScopeRef = {
  kind: string;
  resources?: string[];
};

export type IntentAnnouncePayload = {
  intent_id: string;
  objective?: string;
  scope?: ScopeRef;
  ttl_sec?: number | null;
};

export type IntentWithdrawPayload = {
  intent_id: string;
  reason?: string;
};

/**
 * Per-direction dependency-breakage entry (v0.2.3+).
 *
 * ``symbols`` is:
 *   - an array of fully-qualified symbol names that clash (e.g.
 *     ``["utils.foo"]``) — precise symbol-level conflict, UI can show
 *     exactly which names are at risk.
 *   - ``null`` when we fell back to file-level precision (one side didn't
 *     declare ``affects_symbols``, or the importer did a wildcard
 *     ``import`` that we couldn't pin). UI should say "affects your file
 *     X" without naming symbols.
 */
export type DependencyDetailEntry = {
  file: string;
  symbols: string[] | null;
};

/**
 * Directional breakdown of a dependency_breakage conflict.
 *
 * - ``ab``: ``principal_a``'s edits reach these of ``principal_b``'s files.
 * - ``ba``: ``principal_b``'s edits reach these of ``principal_a``'s files.
 *
 * Both arrays are optional: only the active direction(s) are present.
 */
export type DependencyDetail = {
  ab?: DependencyDetailEntry[];
  ba?: DependencyDetailEntry[];
};

export type ConflictReportPayload = {
  conflict_id: string;
  category?: string;
  severity?: string;
  principal_a?: string;
  principal_b?: string;
  intent_a?: string;
  intent_b?: string;
  /** v0.2.3+: populated only for ``category === "dependency_breakage"``. */
  dependency_detail?: DependencyDetail;
};

/**
 * v0.2.5+ INTENT_DEFERRED — a principal observed an existing intent on
 * ``scope`` and chose to yield without announcing one of their own.
 * Unlike CONFLICT_REPORT (which has two opposing parties), this is a
 * one-sided yield notification.
 *
 * Two flavours of envelope share this payload type:
 *   * **Active** — emitted when the deferral is created. ``status`` is
 *     absent or "active"; the full record (scope, observed_intent_ids,
 *     reason, expires_at) is present.
 *   * **Resolved/expired** — emitted when the coordinator clears the
 *     deferral (the observed intents all terminated, the principal
 *     announced anyway, or TTL fired). ``status`` is "resolved" or
 *     "expired"; only ``deferral_id`` + ``principal_id`` are guaranteed.
 */
export type IntentDeferredPayload = {
  deferral_id: string;
  principal_id?: string;
  /** Present on active deferrals. */
  scope?: ScopeRef;
  reason?: string;
  observed_intent_ids?: string[];
  observed_principals?: string[];
  /** ISO timestamp; client uses this to render a TTL countdown. */
  expires_at?: string | null;
  /** Absent / "active" / "resolved" / "expired". */
  status?: string;
};

export type ParticipantUpdatePayload = {
  principal_id: string;
  status?: string;
  active_intent_id?: string | null;
  display_name?: string;
  principal_type?: string;
  roles?: string[];
  last_seen?: string;
};

export type ProtocolErrorPayload = {
  error_code?: string;
  message?: string;
  original_message_id?: string;
};

/**
 * Bridge-synthesized lifecycle notifications — NOT part of the core MPAC
 * spec. Backend HTTP routes (delete/reset/file write) emit a PROJECT_EVENT
 * envelope so connected browsers can react to side effects that wouldn't
 * otherwise reach them through the protocol envelopes (which are scoped to
 * coordination, not file persistence).
 *
 * Switch on ``payload.kind``:
 *   - ``file_changed``   — payload also has ``path`` and ``updated_at``.
 *                          Frontend re-fetches the file content if it's
 *                          currently open in the editor.
 *   - ``file_deleted``   — payload also has ``path``. Frontend drops it
 *                          from the file list and closes the tab if open.
 *   - ``reset_to_seed``  — payload has ``paths`` (array). Frontend reloads
 *                          the file list and any open file contents.
 *   - ``project_deleted``— payload has ``project_id`` + ``project_name``.
 *                          Frontend redirects to /projects.
 */
export type ProjectEventPayload =
  | { kind: "file_changed"; path: string; updated_at: string }
  | { kind: "file_deleted"; path: string }
  | { kind: "reset_to_seed"; paths: string[] }
  | { kind: "project_deleted"; project_id: number; project_name: string };

// Frontend-facing action vocabulary (must match
// `api/mpac_bridge.browser_action_to_envelope`).

export type BeginTaskAction = {
  action: "begin_task";
  intent_id: string;
  objective?: string;
  files: string[];
};
export type YieldTaskAction = {
  action: "yield_task";
  intent_id: string;
  reason?: string;
};
export type AckConflictAction = {
  action: "ack_conflict";
  conflict_id: string;
};
export type HeartbeatAction = {
  action: "heartbeat";
  status?: string;
  active_intent_id?: string | null;
};

export type BrowserAction =
  | BeginTaskAction
  | YieldTaskAction
  | AckConflictAction
  | HeartbeatAction;
