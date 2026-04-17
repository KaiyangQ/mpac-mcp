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

export type ConflictReportPayload = {
  conflict_id: string;
  category?: string;
  severity?: string;
  principal_a?: string;
  principal_b?: string;
  intent_a?: string;
  intent_b?: string;
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
