"use client";
// React hook that manages a single browser's connection to the MPAC
// coordinator via our FastAPI bridge. Owns the WebSocket lifecycle,
// parses incoming MPAC envelopes, and exposes a typed surface the
// workspace page consumes.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type BrowserAction,
  type ConflictReportPayload,
  type IntentAnnouncePayload,
  type IntentDeferredPayload,
  type IntentWithdrawPayload,
  type MpacEnvelope,
  type ParticipantUpdatePayload,
  type ProjectEventPayload,
  type ProtocolErrorPayload,
  type SessionInfoPayload,
} from "./envelope-types";
import { API_URL, getStoredJwt } from "./api";

export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "closed"
  | "error";

export type LiveParticipant = {
  principal_id: string;
  display_name: string;
  principal_type: "human" | "agent" | string;
  is_agent: boolean;
  is_you: boolean;
  online: boolean;
  roles: string[];
  /** Current intent they've announced, if any. */
  active_intent?: IntentAnnouncePayload;
};

export type LiveConflict = {
  conflict_id: string;
  category: string;
  severity?: string;
  principal_a: string;
  principal_b: string;
  intent_a: string;
  intent_b: string;
  /** v0.2.3+: symbol-level breakdown for dependency_breakage. */
  dependency_detail?: import("./envelope-types").DependencyDetail;
};

/**
 * v0.2.5+ — a one-sided yield record. The deferring principal saw existing
 * intents on ``files`` (via check_overlap or list_active_intents) and chose
 * to back off without announcing. Distinct from LiveConflict: no opposing
 * intent_id pair, no severity, just a yield notification.
 */
export type LiveDeferral = {
  deferral_id: string;
  principal_id: string;
  files: string[];
  reason?: string;
  observed_intent_ids: string[];
  observed_principals: string[];
  /** epoch ms; computed client-side from expires_at, used for TTL countdown. */
  expires_at_ms?: number;
};

export type MpacSessionState = {
  status: ConnectionStatus;
  participants: LiveParticipant[];
  conflicts: LiveConflict[];
  /**
   * v0.2.5+ active yield records (INTENT_DEFERRED). Distinct from conflicts:
   * a deferral is one-sided ("Bob saw Alice and yielded") and auto-clears
   * when the observed intents terminate or TTL expires.
   */
  deferrals: LiveDeferral[];
  /** Intents we ourselves have open, keyed by intent_id. */
  myIntents: Record<string, IntentAnnouncePayload>;
  /** Last protocol-level error, if any. */
  lastError?: ProtocolErrorPayload;
  /** True once SESSION_INFO landed — actions are safe to send. */
  joined: boolean;
};

export type MpacSessionActions = {
  /** Start an intent on the given files. Returns the generated intent_id. */
  beginTask: (files: string[], objective?: string) => string | null;
  /** End a prior intent. */
  yieldTask: (intentId: string, reason?: string) => void;
  /** Acknowledge a detected conflict. */
  ackConflict: (conflictId: string) => void;
};

export type UseMpacSessionOpts = {
  projectId: number;
  selfPrincipalId: string;
  /** Pass the logged-in user's display_name so we can tag "(you)" client-side. */
  selfDisplayName: string;
  enabled?: boolean;
  /**
   * Callback for backend-synthesized lifecycle notifications (PROJECT_EVENT
   * envelopes — file_changed, file_deleted, reset_to_seed, project_deleted).
   * The hook itself only forwards them; the page decides what to do with
   * each kind (refetch a file, redirect, etc.). Passing ``undefined`` makes
   * the hook silently ignore these envelopes — convenient for surfaces
   * that don't need them (e.g. unit tests).
   */
  onProjectEvent?: (event: ProjectEventPayload) => void;
};

const RECONNECT_DELAYS_MS = [500, 1000, 2000, 4000, 8000, 15000];

function randomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  }
  return Math.random().toString(36).slice(2, 14);
}

function wsUrlFromApi(apiUrl: string): string {
  // API_URL is e.g. http://127.0.0.1:8001 — translate scheme to ws/wss.
  if (apiUrl.startsWith("https://")) return "wss://" + apiUrl.slice(8);
  if (apiUrl.startsWith("http://")) return "ws://" + apiUrl.slice(7);
  return apiUrl;
}

export function useMpacSession({
  projectId,
  selfPrincipalId,
  selfDisplayName,
  enabled = true,
  onProjectEvent,
}: UseMpacSessionOpts): MpacSessionState & MpacSessionActions {
  // Stable ref so handleEnvelope doesn't have to take onProjectEvent as a
  // dep (would re-create the WebSocket connect callback on every render
  // that handed in a fresh inline function).
  const onProjectEventRef = useRef(onProjectEvent);
  useEffect(() => {
    onProjectEventRef.current = onProjectEvent;
  }, [onProjectEvent]);
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [participants, setParticipants] = useState<LiveParticipant[]>([]);
  const [conflicts, setConflicts] = useState<LiveConflict[]>([]);
  const [deferrals, setDeferrals] = useState<LiveDeferral[]>([]);
  const [myIntents, setMyIntents] = useState<Record<string, IntentAnnouncePayload>>({});
  const [lastError, setLastError] = useState<ProtocolErrorPayload | undefined>();
  const [joined, setJoined] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closedByUserRef = useRef(false);
  const connectRef = useRef<() => void>(() => {});
  // Stable refs so send() doesn't stale-close.
  const selfPrincipalRef = useRef(selfPrincipalId);
  useEffect(() => {
    selfPrincipalRef.current = selfPrincipalId;
  }, [selfPrincipalId]);
  const selfNameRef = useRef(selfDisplayName);
  useEffect(() => {
    selfNameRef.current = selfDisplayName;
  }, [selfDisplayName]);

  // ─── Participant table helpers ──────────────────────────

  const upsertParticipants = useCallback(
    (
      incoming: Array<Partial<LiveParticipant> & { principal_id: string }>,
    ) => {
      setParticipants((prev) => {
        const map = new Map(prev.map((p) => [p.principal_id, p]));
        for (const raw of incoming) {
          const existing = map.get(raw.principal_id);
          const merged: LiveParticipant = {
            principal_id: raw.principal_id,
            display_name:
              raw.display_name ?? existing?.display_name ?? raw.principal_id,
            principal_type:
              raw.principal_type ?? existing?.principal_type ?? "human",
            is_agent:
              raw.is_agent ??
              existing?.is_agent ??
              (raw.principal_type === "agent"),
            is_you: raw.principal_id === selfPrincipalRef.current,
            online: raw.online ?? existing?.online ?? true,
            roles: raw.roles ?? existing?.roles ?? [],
            active_intent: raw.active_intent ?? existing?.active_intent,
          };
          map.set(raw.principal_id, merged);
        }
        return Array.from(map.values());
      });
    },
    [],
  );

  const updateParticipantIntent = useCallback(
    (principalId: string, intent: IntentAnnouncePayload | undefined) => {
      setParticipants((prev) =>
        prev.map((p) =>
          p.principal_id === principalId ? { ...p, active_intent: intent } : p,
        ),
      );
    },
    [],
  );

  const markParticipantOffline = useCallback((principalId: string) => {
    setParticipants((prev) => {
      const existing = prev.find((p) => p.principal_id === principalId);
      // Agents are ephemeral — when they leave, they're gone; keep the
      // panel tidy by dropping them entirely instead of piling up as
      // "offline" on every chat turn (each turn uses a fresh principal_id).
      if (existing?.is_agent) {
        return prev.filter((p) => p.principal_id !== principalId);
      }
      // Humans stay as offline so teammates can see "was here recently".
      return prev.map((p) =>
        p.principal_id === principalId
          ? { ...p, online: false, active_intent: undefined }
          : p,
      );
    });
  }, []);

  // ─── Envelope dispatch ──────────────────────────────────

  const handleEnvelope = useCallback(
    (env: MpacEnvelope) => {
      switch (env.message_type) {
        case "SESSION_INFO": {
          const p = env.payload as SessionInfoPayload;
          if (p.participants) {
            upsertParticipants(
              p.participants.map((pp) => ({
                principal_id: pp.principal_id,
                display_name: pp.display_name,
                principal_type: pp.principal_type,
                is_agent: pp.principal_type === "agent",
                online: true,
                roles: pp.roles ?? [],
              })),
            );
          }
          // Also make sure *we* appear immediately.
          upsertParticipants([
            {
              principal_id: selfPrincipalRef.current,
              display_name: selfNameRef.current,
              principal_type: "human",
              is_agent: false,
              online: true,
            },
          ]);
          setJoined(true);
          break;
        }
        case "PARTICIPANT_UPDATE": {
          const p = env.payload as ParticipantUpdatePayload;
          if (p.status === "offline") {
            // Offline notice — delegate to the shared handler so agents get
            // dropped while humans stay as "offline".
            markParticipantOffline(p.principal_id);
          } else {
            upsertParticipants([
              {
                principal_id: p.principal_id,
                display_name: p.display_name,
                principal_type: p.principal_type,
                is_agent: p.principal_type === "agent",
                online: true,
                roles: p.roles,
              },
            ]);
          }
          break;
        }
        case "INTENT_ANNOUNCE": {
          const p = env.payload as IntentAnnouncePayload;
          const pid = env.sender.principal_id;
          // Don't pass display_name here — if we already have one (from
          // SESSION_INFO or a prior PARTICIPANT_UPDATE) the upsert keeps it;
          // otherwise it falls back to principal_id until PARTICIPANT_UPDATE
          // arrives. Passing a value would clobber the real display name.
          upsertParticipants([
            {
              principal_id: pid,
              principal_type: env.sender.principal_type,
              is_agent: env.sender.principal_type === "agent",
              online: true,
            },
          ]);
          updateParticipantIntent(pid, p);
          if (pid === selfPrincipalRef.current) {
            setMyIntents((prev) => ({ ...prev, [p.intent_id]: p }));
          }
          break;
        }
        case "INTENT_WITHDRAW": {
          const p = env.payload as IntentWithdrawPayload;
          const pid = env.sender.principal_id;
          updateParticipantIntent(pid, undefined);
          // Drop any conflicts that referenced this intent.
          setConflicts((prev) =>
            prev.filter(
              (c) => c.intent_a !== p.intent_id && c.intent_b !== p.intent_id,
            ),
          );
          if (pid === selfPrincipalRef.current) {
            setMyIntents((prev) => {
              const next = { ...prev };
              delete next[p.intent_id];
              return next;
            });
          }
          break;
        }
        case "CONFLICT_REPORT": {
          const p = env.payload as ConflictReportPayload;
          if (!p.conflict_id) break;
          setConflicts((prev) => {
            if (prev.some((c) => c.conflict_id === p.conflict_id)) return prev;
            return [
              ...prev,
              {
                conflict_id: p.conflict_id,
                category: p.category ?? "unknown",
                severity: p.severity,
                principal_a: p.principal_a ?? "",
                principal_b: p.principal_b ?? "",
                intent_a: p.intent_a ?? "",
                intent_b: p.intent_b ?? "",
                dependency_detail: p.dependency_detail,
              },
            ];
          });
          break;
        }
        case "CONFLICT_ACK":
        case "RESOLUTION": {
          const cid = (env.payload as { conflict_id?: string }).conflict_id;
          if (cid) {
            setConflicts((prev) =>
              prev.filter((c) => c.conflict_id !== cid),
            );
          }
          break;
        }
        case "INTENT_DEFERRED": {
          // v0.2.5+: a peer announced "I saw an existing intent on this
          // file and yielded without claiming". Two flavours share this
          // case — active (full record, render a chip) and resolved/
          // expired (drop the chip).
          const p = env.payload as IntentDeferredPayload;
          if (!p.deferral_id) break;
          if (p.status === "resolved" || p.status === "expired") {
            setDeferrals((prev) =>
              prev.filter((d) => d.deferral_id !== p.deferral_id),
            );
            break;
          }
          // Active deferral.
          const files = (p.scope?.resources ?? []).slice();
          const expiresAtMs = p.expires_at
            ? Date.parse(p.expires_at)
            : undefined;
          setDeferrals((prev) => {
            // Replace any existing entry with the same deferral_id
            // (idempotent broadcast retries).
            const without = prev.filter(
              (d) => d.deferral_id !== p.deferral_id,
            );
            return [
              ...without,
              {
                deferral_id: p.deferral_id,
                principal_id: p.principal_id ?? "",
                files,
                reason: p.reason,
                observed_intent_ids: p.observed_intent_ids ?? [],
                observed_principals: p.observed_principals ?? [],
                expires_at_ms: Number.isFinite(expiresAtMs)
                  ? (expiresAtMs as number)
                  : undefined,
              },
            ];
          });
          break;
        }
        case "GOODBYE": {
          markParticipantOffline(env.sender.principal_id);
          break;
        }
        case "PROTOCOL_ERROR": {
          setLastError(env.payload as ProtocolErrorPayload);
          break;
        }
        case "PROJECT_EVENT": {
          // Bridge-synthesized lifecycle notice — forward to the page so
          // it can refetch a file, drop one, redirect on delete, etc.
          // The hook itself doesn't touch DOM state for these; that's
          // the page's responsibility (file tree, editor, router).
          const cb = onProjectEventRef.current;
          if (cb) {
            try {
              cb(env.payload as ProjectEventPayload);
            } catch (err) {
              console.error("onProjectEvent handler threw", err);
            }
          }
          break;
        }
        default:
          // Ignore HEARTBEAT echoes etc.
          break;
      }
    },
    [markParticipantOffline, updateParticipantIntent, upsertParticipants],
  );

  // ─── Connection management ──────────────────────────────

  const connect = useCallback(() => {
    if (!enabled) return;
    // We still gate on getStoredJwt() so we don't open a doomed WS before
    // the user has logged in — but the JWT itself no longer rides in the
    // URL. The browser sends the ``mpac_jwt`` HttpOnly cookie set on
    // /login + /register automatically on the upgrade; the backend reads
    // it instead of ``?token=``. Closes the URL-leak surface flagged in
    // the 2026-04-25 v2 review (proxy logs, browser history, ``curl -v``).
    const jwt = getStoredJwt();
    if (!jwt) return;

    const url = `${wsUrlFromApi(API_URL)}/ws/session/${projectId}`;
    setStatus(attemptRef.current === 0 ? "connecting" : "reconnecting");

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      setStatus("connected");
    };
    ws.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data) as MpacEnvelope;
        handleEnvelope(parsed);
      } catch {
        /* non-JSON frame — ignore */
      }
    };
    ws.onerror = () => {
      setStatus("error");
    };
    ws.onclose = () => {
      wsRef.current = null;
      setJoined(false);
      if (closedByUserRef.current) {
        setStatus("closed");
        return;
      }
      // Exponential-ish backoff reconnect.
      const delay =
        RECONNECT_DELAYS_MS[
          Math.min(attemptRef.current, RECONNECT_DELAYS_MS.length - 1)
        ];
      attemptRef.current += 1;
      setStatus("reconnecting");
      reconnectTimerRef.current = setTimeout(() => connectRef.current(), delay);
    };
  }, [enabled, projectId, handleEnvelope]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    closedByUserRef.current = false;
    const startupTimer = setTimeout(() => connectRef.current(), 0);
    return () => {
      closedByUserRef.current = true;
      clearTimeout(startupTimer);
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  // ─── Outbound actions ───────────────────────────────────

  const send = useCallback((action: BrowserAction) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(action));
    return true;
  }, []);

  const beginTask = useCallback(
    (files: string[], objective?: string): string | null => {
      if (files.length === 0) return null;
      const intent_id = `intent-${randomId()}`;
      // Optimistically add to my intents so UI can reflect immediately.
      const optimistic: IntentAnnouncePayload = {
        intent_id,
        objective,
        scope: { kind: "file_set", resources: files },
      };
      setMyIntents((prev) => ({ ...prev, [intent_id]: optimistic }));
      updateParticipantIntent(selfPrincipalRef.current, optimistic);
      const ok = send({
        action: "begin_task",
        intent_id,
        objective,
        files,
      });
      return ok ? intent_id : null;
    },
    [send, updateParticipantIntent],
  );

  const yieldTask = useCallback(
    (intentId: string, reason?: string) => {
      // Optimistic local clear.
      setMyIntents((prev) => {
        const next = { ...prev };
        delete next[intentId];
        return next;
      });
      updateParticipantIntent(selfPrincipalRef.current, undefined);
      setConflicts((prev) =>
        prev.filter(
          (c) => c.intent_a !== intentId && c.intent_b !== intentId,
        ),
      );
      send({ action: "yield_task", intent_id: intentId, reason });
    },
    [send, updateParticipantIntent],
  );

  const ackConflict = useCallback(
    (conflictId: string) => {
      setConflicts((prev) =>
        prev.filter((c) => c.conflict_id !== conflictId),
      );
      send({ action: "ack_conflict", conflict_id: conflictId });
    },
    [send],
  );

  // Client-side TTL sweep: if a deferral's expires_at_ms is in the past,
  // drop it locally. Belt-and-suspenders against missed expired-broadcasts
  // (relay reconnect race, etc.).
  useEffect(() => {
    if (deferrals.length === 0) return;
    const now = Date.now();
    const next = deferrals.filter(
      (d) => d.expires_at_ms === undefined || d.expires_at_ms > now,
    );
    if (next.length !== deferrals.length) {
      setDeferrals(next);
      return;
    }
    const earliest = deferrals
      .map((d) => d.expires_at_ms)
      .filter((t): t is number => Number.isFinite(t))
      .reduce((a, b) => Math.min(a, b), Number.POSITIVE_INFINITY);
    if (!Number.isFinite(earliest)) return;
    const wait = Math.max(500, earliest - now + 100);
    const timer = setTimeout(
      () => setDeferrals((prev) =>
        prev.filter(
          (d) =>
            d.expires_at_ms === undefined || d.expires_at_ms > Date.now(),
        ),
      ),
      wait,
    );
    return () => clearTimeout(timer);
  }, [deferrals]);

  return useMemo(
    () => ({
      status,
      participants,
      conflicts,
      deferrals,
      myIntents,
      lastError,
      joined,
      beginTask,
      yieldTask,
      ackConflict,
    }),
    [
      status, participants, conflicts, deferrals, myIntents, lastError, joined,
      beginTask, yieldTask, ackConflict,
    ],
  );
}
