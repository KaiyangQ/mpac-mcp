"use client";

import { use, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { Group, Panel, Separator } from "react-resizable-panels";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronLeft,
  File as FileIcon,
  Folder,
  Pencil,
  Share2,
} from "lucide-react";
import { api, ApiError, type Project, type TokenResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useRequireAuth } from "@/lib/redirect-hooks";
import { InviteModal } from "@/components/invite-modal";
import { CommandPalette } from "@/components/command-palette";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import {
  useMpacSession,
  type ConnectionStatus,
  type LiveConflict,
  type LiveParticipant,
} from "@/lib/mpac-session";

// Monaco must be loaded client-side only (no SSR)
const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

// ── Mock file tree + code (Phase D scope: real presence + intents,
//    but file content + tree stay mock until Phase F) ────────────────

// Demo project: "Task API" — a tiny Flask REST API for collaborative editing.
// Chosen so there are natural overlapping concerns (auth + validators +
// endpoints) to drive realistic MPAC conflict scenarios.

type FileNode = { name: string; path: string; children?: FileNode[] };

const MOCK_FILES: FileNode[] = [
  { name: "src/", path: "src/", children: [
    { name: "auth.py", path: "src/auth.py" },
    { name: "api.py", path: "src/api.py" },
    { name: "models.py", path: "src/models.py" },
    { name: "utils/", path: "src/utils/", children: [
      { name: "helpers.py", path: "src/utils/helpers.py" },
      { name: "validators.py", path: "src/utils/validators.py" },
    ]},
  ]},
  { name: "tests/", path: "tests/", children: [
    { name: "test_auth.py", path: "tests/test_auth.py" },
    { name: "test_api.py", path: "tests/test_api.py" },
  ]},
  { name: "README.md", path: "README.md" },
];

const MOCK_CODE: Record<string, string> = {
  "src/auth.py": `"""JWT-based auth for the Task API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from flask import current_app, request

ALG = "HS256"
ACCESS_TTL = timedelta(minutes=15)


def issue_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + ACCESS_TTL,
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=ALG)


def verify_token(token: str) -> Optional[dict]:
    """Verify a JWT and return the claims dict, or None on failure."""
    try:
        return jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[ALG],
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def current_user() -> Optional[dict]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return verify_token(auth[7:])
`,
  "src/api.py": `"""Task CRUD endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from .auth import current_user
from .models import Task, store
from .utils.validators import validate_task_payload

bp = Blueprint("api", __name__, url_prefix="/api/tasks")


@bp.get("")
def list_tasks():
    user = current_user()
    if not user:
        return {"error": "unauthorized"}, 401
    return jsonify([t.to_dict() for t in store.for_user(user["sub"])])


@bp.post("")
def create_task():
    user = current_user()
    if not user:
        return {"error": "unauthorized"}, 401
    body = request.get_json(silent=True) or {}
    err = validate_task_payload(body)
    if err:
        return {"error": err}, 400
    task = Task(owner_id=user["sub"], title=body["title"], done=False)
    store.add(task)
    return task.to_dict(), 201


@bp.delete("/<int:task_id>")
def delete_task(task_id: int):
    user = current_user()
    if not user:
        return {"error": "unauthorized"}, 401
    if not store.delete(task_id, owner_id=user["sub"]):
        return {"error": "not found"}, 404
    return "", 204
`,
  "src/models.py": `"""In-memory Task store for the demo."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from itertools import count
from typing import Dict, List, Optional

_ids = count(1)


@dataclass
class Task:
    owner_id: str
    title: str
    done: bool = False
    id: int = field(default_factory=lambda: next(_ids))

    def to_dict(self) -> dict:
        return asdict(self)


class TaskStore:
    def __init__(self) -> None:
        self._by_id: Dict[int, Task] = {}

    def add(self, task: Task) -> None:
        self._by_id[task.id] = task

    def for_user(self, owner_id: str) -> List[Task]:
        return [t for t in self._by_id.values() if t.owner_id == owner_id]

    def delete(self, task_id: int, *, owner_id: str) -> bool:
        t = self._by_id.get(task_id)
        if t is None or t.owner_id != owner_id:
            return False
        del self._by_id[task_id]
        return True


store = TaskStore()
`,
  "src/utils/helpers.py": `"""Small formatting helpers used across the API layer."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_iso() -> str:
    """RFC 3339 timestamp for the current moment."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))
`,
  "src/utils/validators.py": `"""Payload validation for the Task API."""
from __future__ import annotations

from typing import Optional

MAX_TITLE_LEN = 200


def validate_task_payload(body: dict) -> Optional[str]:
    """Return an error string if invalid, else None."""
    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return "title is required and must be a non-empty string"
    if len(title) > MAX_TITLE_LEN:
        return f"title exceeds {MAX_TITLE_LEN} chars"
    done = body.get("done", False)
    if not isinstance(done, bool):
        return "done must be a boolean"
    return None
`,
  "tests/test_auth.py": `"""Auth tests — currently only happy-path; refresh token coverage TODO."""
from __future__ import annotations

import time

import pytest
from flask import Flask

from src.auth import issue_token, verify_token


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"
    with app.app_context():
        yield app


def test_issue_and_verify_roundtrip(app):
    token = issue_token(42, "a@b.com")
    claims = verify_token(token)
    assert claims["sub"] == "42"
    assert claims["email"] == "a@b.com"


def test_invalid_token_returns_none(app):
    assert verify_token("garbage") is None
`,
  "tests/test_api.py": `"""Endpoint tests. Coverage is thin — expand this!"""
from __future__ import annotations

import pytest
from flask import Flask

from src.api import bp as api_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"
    app.register_blueprint(api_bp)
    with app.test_client() as c:
        yield c


def test_list_unauthorized(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 401
`,
  "README.md": `# Task API — MPAC demo project

Tiny Flask-based task tracker used to exercise the Multi-Principal Agent
Coordination protocol. Humans and AI agents share the same repo; MPAC keeps
them from stepping on each other's toes via explicit intent announcements
and scope-overlap detection.

## Module map

\`\`\`
src/
├── auth.py         # JWT issue / verify (no refresh tokens yet)
├── api.py          # Blueprint with /api/tasks CRUD
├── models.py       # In-memory Task dataclass + TaskStore
└── utils/
    ├── helpers.py      # clamp, utc_iso
    └── validators.py   # validate_task_payload

tests/
├── test_auth.py
└── test_api.py
\`\`\`

## Known gaps (good targets for agent work)

- No refresh token flow in \`auth.py\`.
- \`api.py\` is missing \`PUT /api/tasks/<id>\` (update/toggle-done).
- \`validators.py\` doesn't validate \`done\` on partial updates.
- Test coverage in \`test_api.py\` is placeholder-only.
`,
};

// ── Derived helpers ────────────────────────────────────────────────────

/** Find which participant (other than me) is working on this file, if any. */
function findEditor(
  filePath: string,
  participants: LiveParticipant[],
  selfPrincipalId: string,
): LiveParticipant | undefined {
  return participants.find(
    (p) =>
      p.principal_id !== selfPrincipalId &&
      p.active_intent?.scope?.resources?.includes(filePath),
  );
}

/** The intent I have on this file, if any. */
function myIntentOnFile(
  filePath: string,
  myIntents: Record<string, { intent_id: string; scope?: { resources?: string[] } }>,
): string | undefined {
  for (const it of Object.values(myIntents)) {
    if (it.scope?.resources?.includes(filePath)) return it.intent_id;
  }
  return undefined;
}

function connectionLabel(status: ConnectionStatus): { color: string; text: string } {
  switch (status) {
    case "connected":
      return { color: "var(--green)", text: "Connected" };
    case "connecting":
      return { color: "var(--yellow)", text: "Connecting…" };
    case "reconnecting":
      return { color: "var(--yellow)", text: "Reconnecting…" };
    case "error":
      return { color: "var(--red)", text: "Error" };
    case "closed":
      return { color: "#484f58", text: "Disconnected" };
    default:
      return { color: "#484f58", text: "Idle" };
  }
}

// ── Sub-components ─────────────────────────────────────────────────────

function FileTree({
  files,
  activePath,
  participants,
  selfPrincipalId,
  myIntents,
  onSelect,
  depth = 0,
}: {
  files: FileNode[];
  activePath: string | null;
  participants: LiveParticipant[];
  selfPrincipalId: string;
  myIntents: Record<string, { intent_id: string; scope?: { resources?: string[] } }>;
  onSelect: (path: string) => void;
  depth?: number;
}) {
  return (
    <div>
      {files.map((f) => {
        const isFile = !f.children;
        const isActive = isFile && f.path === activePath;
        const editor = isFile ? findEditor(f.path, participants, selfPrincipalId) : undefined;
        const iOwnIntent = isFile ? !!myIntentOnFile(f.path, myIntents) : false;
        return (
          <div key={f.path}>
            <div
              role={isFile ? "button" : undefined}
              tabIndex={isFile ? 0 : -1}
              onClick={() => isFile && onSelect(f.path)}
              onKeyDown={(e) => {
                if (isFile && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault();
                  onSelect(f.path);
                }
              }}
              className={`flex items-center gap-1.5 py-1 text-[13px] rounded transition-colors ${
                isFile ? "cursor-pointer hover:bg-[var(--bg-tertiary)]" : "cursor-default"
              } ${isActive ? "bg-[var(--bg-tertiary)] text-[var(--accent)]" : "text-[var(--text-primary)]"}`}
              style={{ paddingLeft: `${depth * 16 + 12}px`, paddingRight: "8px" }}
            >
              <span className="text-[var(--text-secondary)] shrink-0 inline-flex">
                {f.children ? (
                  <Folder className="size-3.5" />
                ) : (
                  <FileIcon className="size-3.5" />
                )}
              </span>
              <span className="flex-1 truncate">{f.name}</span>
              {iOwnIntent && (
                <span
                  className="w-2 h-2 rounded-full bg-[var(--accent)]"
                  title="You're working on this"
                />
              )}
              {editor && !iOwnIntent && (
                <span
                  className={`w-2 h-2 rounded-full ${editor.is_agent ? "bg-[var(--accent)]" : "bg-[var(--green)]"}`}
                  title={`${editor.display_name} is working on this`}
                />
              )}
            </div>
            {f.children && (
              <FileTree
                files={f.children}
                activePath={activePath}
                participants={participants}
                selfPrincipalId={selfPrincipalId}
                myIntents={myIntents}
                onSelect={onSelect}
                depth={depth + 1}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function ConflictCard({
  conflict,
  participants,
  selfPrincipalId,
  myIntentId,
  onAck,
  onYield,
}: {
  conflict: LiveConflict;
  participants: LiveParticipant[];
  selfPrincipalId: string;
  myIntentId?: string;
  onAck: () => void;
  onYield: () => void;
}) {
  const nameOf = (pid: string) =>
    participants.find((p) => p.principal_id === pid)?.display_name ??
    pid.replace(/^user:|^agent:/, "");
  const a = nameOf(conflict.principal_a);
  const b = nameOf(conflict.principal_b);
  const myIntentInConflict =
    conflict.intent_a === myIntentId || conflict.intent_b === myIntentId;

  return (
    <div className="bg-[#f8514910] border border-[#f8514930] rounded-lg p-2.5 mb-2">
      <div className="flex items-center gap-1.5 mb-1.5">
        <AlertTriangle className="size-3.5 text-[var(--red)]" />
        <span className="text-xs font-medium text-[var(--red)]">
          {conflict.category === "scope_overlap" ? "Scope overlap" : conflict.category}
        </span>
        {conflict.severity && (
          <span className="text-[10px] text-[var(--text-secondary)] ml-auto">
            {conflict.severity}
          </span>
        )}
      </div>
      <div className="text-xs text-[var(--text-primary)] mb-2">
        <span className="font-medium">{a}</span>
        <span className="text-[var(--text-secondary)]"> ↔ </span>
        <span className="font-medium">{b}</span>
      </div>
      <div className="flex gap-1.5">
        <Button
          size="xs"
          variant="secondary"
          onClick={onAck}
          className="bg-[var(--bg-tertiary)] hover:bg-[var(--border)] border border-[var(--border)] text-[var(--text-primary)]"
        >
          Acknowledge
        </Button>
        {myIntentInConflict && (
          <Button
            size="xs"
            variant="secondary"
            onClick={onYield}
            className="bg-[var(--yellow)]/20 hover:bg-[var(--yellow)]/30 border border-[var(--yellow)]/40 text-[var(--yellow)]"
          >
            Yield
          </Button>
        )}
      </div>
    </div>
  );
}

function CollabPanel({
  participants,
  conflicts,
  selfPrincipalId,
  myIntents,
  onAck,
  onYield,
}: {
  participants: LiveParticipant[];
  conflicts: LiveConflict[];
  selfPrincipalId: string;
  myIntents: Record<string, { intent_id: string; scope?: { resources?: string[] } }>;
  onAck: (id: string) => void;
  onYield: (intentId: string) => void;
}) {
  // Show online participants first, then offline — keep self pinned to top.
  const sorted = [...participants].sort((a, b) => {
    if (a.is_you !== b.is_you) return a.is_you ? -1 : 1;
    if (a.online !== b.online) return a.online ? -1 : 1;
    return a.display_name.localeCompare(b.display_name);
  });

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="p-3 border-b border-[var(--border)]">
        <h3 className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2.5">
          Who&apos;s Working
        </h3>
        {sorted.length === 0 ? (
          <div className="text-xs text-[var(--text-secondary)] py-2">Connecting…</div>
        ) : (
          <div className="space-y-2.5">
            {sorted.map((p) => (
              <div key={p.principal_id} className="flex items-start gap-2.5">
                <div className="relative mt-0.5 flex-shrink-0">
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium ${
                      p.is_agent
                        ? "bg-[#1f2937] text-[var(--accent)] ring-1 ring-[var(--accent)]/30"
                        : "bg-[var(--bg-tertiary)] text-[var(--text-primary)]"
                    }`}
                  >
                    {p.is_agent ? (
                      <Bot className="size-4" />
                    ) : (
                      p.display_name[0]?.toUpperCase() ?? "?"
                    )}
                  </div>
                  <span
                    className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-[var(--bg-secondary)] ${
                      p.online ? "bg-[var(--green)]" : "bg-[#484f58]"
                    }`}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium truncate">
                      {p.display_name}
                    </span>
                    {p.is_you && (
                      <span className="text-[10px] text-[var(--text-secondary)]">
                        (you)
                      </span>
                    )}
                    {p.is_agent && (
                      <span className="text-[9px] px-1 py-px bg-[#1f2937] text-[var(--accent)] rounded">
                        AI
                      </span>
                    )}
                  </div>
                  {p.active_intent?.scope?.resources?.length ? (
                    <div className="flex items-center gap-1 text-xs text-[var(--text-secondary)] truncate mt-0.5">
                      <Pencil className="size-3 shrink-0" />
                      <span className="truncate">
                        {p.active_intent.scope.resources[0]}
                        {p.active_intent.scope.resources.length > 1 &&
                          ` +${p.active_intent.scope.resources.length - 1}`}
                      </span>
                    </div>
                  ) : p.online ? (
                    <div className="text-xs text-[var(--text-secondary)] mt-0.5">idle</div>
                  ) : (
                    <div className="text-xs text-[#484f58] mt-0.5">offline</div>
                  )}
                  {p.active_intent?.objective && (
                    <div className="text-[11px] text-[var(--accent)] truncate mt-0.5 italic">
                      &ldquo;{p.active_intent.objective}&rdquo;
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="p-3">
        <h3 className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2.5">
          Conflicts
        </h3>
        {conflicts.length === 0 ? (
          <div className="flex items-center justify-center gap-1.5 text-xs text-[var(--text-secondary)] py-4">
            <CheckCircle2 className="size-3.5 text-[var(--green)]" />
            No conflicts
          </div>
        ) : (
          conflicts.map((c) => {
            // Figure out my intent_id in this conflict (if any).
            const myIds = new Set(Object.keys(myIntents));
            const myIntentId = myIds.has(c.intent_a)
              ? c.intent_a
              : myIds.has(c.intent_b)
                ? c.intent_b
                : undefined;
            return (
              <ConflictCard
                key={c.conflict_id}
                conflict={c}
                participants={participants}
                selfPrincipalId={selfPrincipalId}
                myIntentId={myIntentId}
                onAck={() => onAck(c.conflict_id)}
                onYield={() => myIntentId && onYield(myIntentId)}
              />
            );
          })
        )}
      </div>
    </div>
  );
}

type ChatTurn = {
  id: string;
  role: "user" | "assistant";
  content: string;
  pending?: boolean;
  error?: boolean;
};

function AiChat({
  projectId,
  userInitial,
}: {
  projectId: number;
  userInitial: string;
}) {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom on new messages.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || busy) return;

    const userTurn: ChatTurn = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    const pendingTurn: ChatTurn = {
      id: `a-${Date.now()}`,
      role: "assistant",
      content: "",
      pending: true,
    };
    setTurns((prev) => [...prev, userTurn, pendingTurn]);
    setInput("");
    setBusy(true);

    try {
      const res = await api.chat(projectId, trimmed);
      setTurns((prev) =>
        prev.map((t) =>
          t.id === pendingTurn.id
            ? { ...t, content: res.reply, pending: false }
            : t,
        ),
      );
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Chat request failed";
      setTurns((prev) =>
        prev.map((t) =>
          t.id === pendingTurn.id
            ? { ...t, content: message, pending: false, error: true }
            : t,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-[var(--border)] flex items-center gap-2 flex-shrink-0">
        <Bot className="size-4 text-[var(--accent)]" />
        <span className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
          AI Assistant
        </span>
        <span className="ml-auto text-[9px] px-1.5 py-0.5 bg-[#1f2937] text-[var(--accent)] rounded-full font-medium">
          Claude
        </span>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0"
      >
        {turns.length === 0 ? (
          <div className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Ask Claude to help with the code. It will join this session as its
            own MPAC participant, announce what files it plans to touch, and
            leave once done — you&apos;ll see it pop up in the panel above.
          </div>
        ) : (
          turns.map((t) => (
            <div key={t.id} className="flex gap-2">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] flex-shrink-0 mt-0.5 ${
                  t.role === "user"
                    ? "bg-[var(--bg-tertiary)] text-[var(--text-primary)] font-medium"
                    : "bg-[#1f2937] text-[var(--accent)] ring-1 ring-[var(--accent)]/30"
                }`}
              >
                {t.role === "user" ? userInitial : <Bot className="size-3.5" />}
              </div>
              <div
                className={`text-[13px] leading-relaxed flex-1 min-w-0 ${
                  t.error
                    ? "text-[var(--red)]"
                    : "text-[var(--text-primary)]"
                }`}
              >
                {t.pending ? (
                  <div className="flex gap-1 items-center h-5">
                    <span
                      className="w-1.5 h-1.5 bg-[var(--accent)] rounded-full animate-bounce"
                      style={{ animationDelay: "0ms" }}
                    />
                    <span
                      className="w-1.5 h-1.5 bg-[var(--accent)] rounded-full animate-bounce"
                      style={{ animationDelay: "150ms" }}
                    />
                    <span
                      className="w-1.5 h-1.5 bg-[var(--accent)] rounded-full animate-bounce"
                      style={{ animationDelay: "300ms" }}
                    />
                    <span className="text-[11px] text-[var(--text-secondary)] ml-1">
                      Claude is working…
                    </span>
                  </div>
                ) : (
                  t.content.split("\n").map((line, i) => (
                    <p key={i} className={line === "" ? "h-2" : "mb-0.5 whitespace-pre-wrap break-words"}>
                      {line}
                    </p>
                  ))
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <form onSubmit={onSubmit} className="p-2 border-t border-[var(--border)] flex-shrink-0">
        <div className="flex gap-2">
          <Input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={busy ? "Claude is working…" : "Ask AI to help with your code..."}
            disabled={busy}
            className="flex-1"
          />
          <Button
            type="submit"
            disabled={busy || !input.trim()}
            className="bg-[#238636] hover:bg-[#2ea043] disabled:bg-[#238636]/50 text-white"
          >
            {busy ? "…" : "Send"}
          </Button>
        </div>
      </form>
    </div>
  );
}

// ── Resize handles for react-resizable-panels v4 Group ────────────────
// The Separator itself is 4px wide/tall (easy to grab on a trackpad) with
// a visible 1px line rendered via ::before down its center.
//
// v4 sets `data-separator="inactive" | "active"` on the root (active = being
// dragged). Hover feedback uses a plain `:hover` selector; drag feedback
// uses the `data-[separator=active]` attribute selector.

function VSplit() {
  return (
    <Separator
      className={
        "relative w-1 cursor-col-resize shrink-0 " +
        "before:content-[''] before:absolute before:inset-y-0 " +
        "before:left-1/2 before:-translate-x-1/2 before:w-px " +
        "before:bg-[var(--border)] before:transition-colors " +
        "hover:before:bg-[var(--accent)] " +
        "data-[separator=active]:before:bg-[var(--accent)] " +
        "data-[separator=active]:before:w-[2px]"
      }
    />
  );
}

function HSplit() {
  return (
    <Separator
      className={
        "relative h-1 cursor-row-resize shrink-0 " +
        "before:content-[''] before:absolute before:inset-x-0 " +
        "before:top-1/2 before:-translate-y-1/2 before:h-px " +
        "before:bg-[var(--border)] before:transition-colors " +
        "hover:before:bg-[var(--accent)] " +
        "data-[separator=active]:before:bg-[var(--accent)] " +
        "data-[separator=active]:before:h-[2px]"
      }
    />
  );
}

// Persist a Group's layout to localStorage under `storageKey`.
// Hook returns the saved layout (if any) and an `onLayoutChanged` callback.
function useStoredLayout(storageKey: string) {
  const [layout, setLayout] = useState<Record<string, number> | undefined>(() => {
    if (typeof window === "undefined") return undefined;
    try {
      const raw = window.localStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : undefined;
    } catch {
      return undefined;
    }
  });
  const save = (next: Record<string, number>) => {
    setLayout(next);
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(next));
    } catch {
      /* quota / disabled — ignore */
    }
  };
  return { layout, save };
}

// ── Main Page ──────────────────────────────────────────────────────────

export default function WorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: idStr } = use(params);
  const projectId = Number(idStr);
  const nextPath = `/projects/${idStr}`;

  const { user, isLoading: authLoading } = useRequireAuth(nextPath);
  const { logout } = useAuth();
  const router = useRouter();

  const [project, setProject] = useState<Project | null>(null);
  const [mpacToken, setMpacToken] = useState<TokenResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showInvite, setShowInvite] = useState(false);
  const [showPalette, setShowPalette] = useState(false);
  const [activePath, setActivePath] = useState<string | null>("src/auth.py");

  // Persisted drag-to-resize layout
  const colsLayout = useStoredLayout("mpac.workspace.cols");
  const rowsLayout = useStoredLayout("mpac.workspace.sidebar-rows");

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const [p, t] = await Promise.all([
          api.getProject(projectId),
          api.getMpacToken(projectId),
        ]);
        if (cancelled) return;
        setProject(p);
        setMpacToken(t);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 401) {
          logout();
          router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
          return;
        }
        setLoadError(
          e instanceof ApiError ? e.message : "Failed to load project",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, projectId, nextPath, logout, router]);

  const selfPrincipalId = user ? `user:${user.user_id}` : "user:?";
  const selfDisplayName = user?.display_name ?? "You";

  const session = useMpacSession({
    projectId,
    selfPrincipalId,
    selfDisplayName,
    enabled: !!user && !!project,
  });

  // When the user opens a file, automatically announce an intent.
  // Any previously held intent on OTHER files gets yielded so we have exactly
  // one "editing this file" intent at a time — this mirrors how a real IDE
  // focuses on one file and keeps the UX simple for the demo.
  useEffect(() => {
    if (!session.joined || !activePath) return;
    // Already holding an intent on this file? Nothing to do.
    const existing = myIntentOnFile(activePath, session.myIntents);
    if (existing) return;
    // Yield any intents on other files first (fire-and-forget).
    for (const intent of Object.values(session.myIntents)) {
      if (!intent.scope?.resources?.includes(activePath)) {
        session.yieldTask(intent.intent_id, "switched file");
      }
    }
    session.beginTask([activePath], `editing ${activePath}`);
    // We intentionally don't depend on `session.myIntents` to avoid loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.joined, activePath]);

  if (authLoading || !user || loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-[var(--bg-primary)] text-[var(--text-secondary)] text-sm">
        Loading workspace…
      </div>
    );
  }

  if (loadError || !project || !mpacToken) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-[var(--bg-primary)] text-[var(--text-primary)] gap-3">
        <AlertTriangle className="size-8 text-[var(--yellow)]" />
        <div className="text-sm">{loadError ?? "Project not available"}</div>
        <Button asChild variant="secondary">
          <Link href="/projects">
            <ChevronLeft className="size-4" />
            Back to projects
          </Link>
        </Button>
      </div>
    );
  }

  const isOwner = project.owner_id === user.user_id;
  const role = mpacToken.roles[0] ?? "contributor";
  const conn = connectionLabel(session.status);
  const onlineCount = session.participants.filter((p) => p.online).length;

  return (
    <div className="h-screen flex flex-col bg-[var(--bg-primary)]">
      {/* Top Bar */}
      <header className="h-12 bg-[var(--bg-secondary)] border-b border-[var(--border)] flex items-center px-4 gap-4 flex-shrink-0">
        <Link
          href="/projects"
          className="inline-flex items-center gap-1 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <ChevronLeft className="size-4" />
          Projects
        </Link>
        <div className="h-4 w-px bg-[var(--border)]" />
        <h1
          className="text-sm font-semibold text-[#e6edf3]"
          title={project.session_id}
        >
          {project.name}
        </h1>
        <div className="flex items-center gap-1 ml-2">
          {session.participants
            .filter((p) => p.online)
            .slice(0, 5)
            .map((p) => (
              <div
                key={p.principal_id}
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium border-2 border-[var(--bg-secondary)] ${
                  p.is_agent
                    ? "bg-[#1f2937] text-[var(--accent)]"
                    : "bg-[var(--bg-tertiary)] text-[var(--text-primary)]"
                }`}
                title={p.display_name}
              >
                {p.is_agent ? (
                  <Bot className="size-3" />
                ) : (
                  p.display_name[0]?.toUpperCase() ?? "?"
                )}
              </div>
            ))}
          <span className="text-xs text-[var(--text-secondary)] ml-1">
            {onlineCount} online
          </span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setShowPalette(true)}
            className="gap-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hidden sm:inline-flex"
            title="Command palette"
          >
            <span className="text-xs">Search</span>
            <Kbd>⌘K</Kbd>
          </Button>
          <span className="text-xs text-[var(--text-secondary)] mr-1">
            {user.display_name}
          </span>
          {isOwner && (
            <Button
              size="sm"
              onClick={() => setShowInvite(true)}
              className="bg-[#238636] hover:bg-[#2ea043] text-white"
            >
              <Share2 className="size-3.5" />
              Invite
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              logout();
              router.replace("/login");
            }}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            Sign out
          </Button>
        </div>
      </header>

      {/* Three-Column Layout — drag the 1px dividers to resize.
          Layout percentages persist per-browser via useStoredLayout. */}
      <Group
        orientation="horizontal"
        defaultLayout={colsLayout.layout}
        onLayoutChanged={colsLayout.save}
        className="flex-1 overflow-hidden"
      >
        {/* Left: file tree */}
        <Panel id="files" defaultSize="15%" minSize="8%" maxSize="30%" collapsible
               className="bg-[var(--bg-secondary)] flex flex-col">
          <div className="px-3 py-2 border-b border-[var(--border)]">
            <span className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
              Files
            </span>
          </div>
          <div className="flex-1 overflow-y-auto py-1">
            <FileTree
              files={MOCK_FILES}
              activePath={activePath}
              participants={session.participants}
              selfPrincipalId={selfPrincipalId}
              myIntents={session.myIntents}
              onSelect={setActivePath}
            />
          </div>
        </Panel>

        <VSplit />

        {/* Center: editor */}
        <Panel id="editor" defaultSize="60%" minSize="25%"
               className="flex flex-col bg-[var(--bg-primary)]">
          <div className="h-9 bg-[var(--bg-secondary)] border-b border-[var(--border)] flex items-center px-2 gap-0.5 flex-shrink-0">
            <div className="flex items-center gap-1.5 px-3 py-1 bg-[var(--bg-primary)] rounded-t border border-[var(--border)] border-b-transparent text-xs">
              <span className="text-[#e6edf3]">{activePath ?? "(no file)"}</span>
            </div>
          </div>
          <div className="flex-1 min-h-0">
            <Editor
              height="100%"
              language={activePath?.endsWith(".md") ? "markdown" : "python"}
              theme="vs-dark"
              path={activePath ?? "untitled"}
              value={activePath ? (MOCK_CODE[activePath] ?? "") : ""}
              options={{
                fontSize: 14,
                minimap: { enabled: false },
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                renderLineHighlight: "gutter",
                padding: { top: 8 },
                fontFamily: "var(--font-mono), 'Fira Code', 'Cascadia Code', monospace",
              }}
            />
          </div>
        </Panel>

        <VSplit />

        {/* Right: collab panel + AI chat, vertically resizable */}
        <Panel id="sidebar" defaultSize="25%" minSize="15%" maxSize="50%" collapsible
               className="bg-[var(--bg-secondary)]">
          <Group
            orientation="vertical"
            defaultLayout={rowsLayout.layout}
            onLayoutChanged={rowsLayout.save}
            className="h-full"
          >
            <Panel id="collab" defaultSize="60%" minSize="20%" className="overflow-hidden">
              <CollabPanel
                participants={session.participants}
                conflicts={session.conflicts}
                selfPrincipalId={selfPrincipalId}
                myIntents={session.myIntents}
                onAck={session.ackConflict}
                onYield={session.yieldTask}
              />
            </Panel>

            <HSplit />

            <Panel id="chat" defaultSize="40%" minSize="15%" className="flex flex-col min-h-0">
              <AiChat
                projectId={project.id}
                userInitial={
                  user.display_name[0]?.toUpperCase() ?? "?"
                }
              />
            </Panel>
          </Group>
        </Panel>
      </Group>

      {/* Status Bar */}
      <footer className="h-6 bg-[var(--bg-secondary)] border-t border-[var(--border)] flex items-center px-3 text-[11px] text-[var(--text-secondary)] gap-3 flex-shrink-0">
        <span className="flex items-center gap-1.5">
          <span
            className="w-2 h-2 rounded-full"
            style={{ background: conn.color }}
          />
          {conn.text}
        </span>
        <span className="text-[var(--border)]">|</span>
        <span className="font-mono truncate max-w-md">
          session: {project.session_id}
        </span>
        <span className="ml-auto">
          {role} · {user.display_name}
        </span>
      </footer>

      <InviteModal
        projectId={project.id}
        projectName={project.name}
        open={showInvite}
        onOpenChange={setShowInvite}
      />

      <CommandPalette
        open={showPalette}
        onOpenChange={setShowPalette}
        files={MOCK_FILES}
        onJumpToFile={setActivePath}
        onOpenInvite={isOwner ? () => setShowInvite(true) : undefined}
        onGotoProjects={() => router.push("/projects")}
        onSignOut={() => {
          logout();
          router.replace("/login");
        }}
        myIntents={session.myIntents}
        conflicts={session.conflicts}
        onYieldIntent={session.yieldTask}
        onAckConflict={session.ackConflict}
      />
    </div>
  );
}
