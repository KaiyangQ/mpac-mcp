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
  LogOut,
  Pencil,
  Share2,
  Trash2,
} from "lucide-react";
import { api, ApiError, type Project, type TokenResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useRequireAuth } from "@/lib/redirect-hooks";
import { InviteModal } from "@/components/invite-modal";
import { NewFileModal } from "@/components/new-file-modal";
import {
  FileContextMenu,
  type FileContextMenuItem,
} from "@/components/file-context-menu";
import { ConnectClaudeModal } from "@/components/connect-claude-modal";
import { DestructiveConfirmModal } from "@/components/destructive-confirm-modal";
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

// ── File tree types + helpers ────────────────────────────────────
//
// Files live server-side (see api/routes/files.py). The backend hands us
// a flat list of paths; we build a tree client-side for rendering and for
// the command palette's fuzzy-match index.

type FileNode = { name: string; path: string; children?: FileNode[] };

/** Build a nested FileNode tree from a flat list of POSIX paths. */
function buildFileTree(paths: string[]): FileNode[] {
  const root: FileNode[] = [];
  const dirIndex = new Map<string, FileNode[]>(); // dirPath → children array
  dirIndex.set("", root);

  // Sort so parents of any directory are visited before its files — makes
  // the dir-creation loop straightforward.
  const sorted = [...paths].sort();
  for (const path of sorted) {
    const segments = path.split("/");
    let parentKey = "";
    for (let i = 0; i < segments.length; i++) {
      const segment = segments[i];
      const isLeaf = i === segments.length - 1;
      const currentKey = parentKey ? `${parentKey}/${segment}` : segment;
      const parentChildren = dirIndex.get(parentKey)!;
      if (isLeaf) {
        if (!parentChildren.some((n) => n.path === path)) {
          parentChildren.push({ name: segment, path });
        }
      } else {
        const dirPath = `${currentKey}/`;
        let dirNode = parentChildren.find((n) => n.path === dirPath);
        if (!dirNode) {
          dirNode = { name: `${segment}/`, path: dirPath, children: [] };
          parentChildren.push(dirNode);
          dirIndex.set(currentKey, dirNode.children!);
        }
      }
      parentKey = currentKey;
    }
  }
  // Sort each level: directories first, then files, each alphabetically.
  const sortLevel = (nodes: FileNode[]) => {
    nodes.sort((a, b) => {
      const aDir = !!a.children;
      const bDir = !!b.children;
      if (aDir !== bDir) return aDir ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    for (const n of nodes) if (n.children) sortLevel(n.children);
  };
  sortLevel(root);
  return root;
}

function languageForPath(path: string): string {
  if (path.endsWith(".md")) return "markdown";
  if (path.endsWith(".json")) return "json";
  if (path.endsWith(".ts") || path.endsWith(".tsx")) return "typescript";
  if (path.endsWith(".js") || path.endsWith(".jsx")) return "javascript";
  if (path.endsWith(".css")) return "css";
  if (path.endsWith(".html")) return "html";
  if (path.endsWith(".sh")) return "shell";
  if (path.endsWith(".yml") || path.endsWith(".yaml")) return "yaml";
  return "python";
}


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
  onDelete,
  onContextMenu,
  depth = 0,
}: {
  files: FileNode[];
  activePath: string | null;
  participants: LiveParticipant[];
  selfPrincipalId: string;
  myIntents: Record<string, { intent_id: string; scope?: { resources?: string[] } }>;
  onSelect: (path: string) => void;
  onDelete?: (path: string) => void;
  /** Called when the user right-clicks a row. ``isFolder`` lets the
   * parent pre-fill a "New file in <folder>/" path when appropriate. */
  onContextMenu?: (
    e: React.MouseEvent,
    path: string,
    isFolder: boolean,
  ) => void;
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
              onContextMenu={
                onContextMenu
                  ? (e) => {
                      // Stop the browser's native menu AND the bubble
                      // so the Files-panel-wide handler doesn't also
                      // fire (which would override our row-specific
                      // target with "empty area").
                      e.preventDefault();
                      e.stopPropagation();
                      onContextMenu(e, f.path, !isFile);
                    }
                  : undefined
              }
              className={`group flex items-center gap-1.5 py-1 text-[13px] rounded transition-colors ${
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
              {isFile && onDelete && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(f.path);
                  }}
                  className="opacity-0 group-hover:opacity-100 text-[var(--text-secondary)] hover:text-[var(--red)] text-xs leading-none shrink-0"
                  title={`Delete ${f.path}`}
                  aria-label={`Delete ${f.path}`}
                >
                  ×
                </button>
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
                onDelete={onDelete}
                onContextMenu={onContextMenu}
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

  // v0.2.3: category label — prefer "Dependency" over the raw
  // ``dependency_breakage`` enum, matches the conversational tone of the
  // panel. Unknown categories pass through verbatim so we never hide a
  // new category behind a generic label.
  const categoryLabel =
    conflict.category === "scope_overlap"
      ? "Scope overlap"
      : conflict.category === "dependency_breakage"
        ? "Dependency"
        : conflict.category;

  // Flatten dependency_detail (ab/ba directions) into render-friendly
  // rows with the editor + consumer names resolved. Each row describes
  // "[editor]'s edits to [symbols] affect [consumer]'s [file]".
  const dependencyRows: Array<{
    editor: string;
    consumer: string;
    file: string;
    symbols: string[] | null;
  }> = [];
  if (conflict.category === "dependency_breakage" && conflict.dependency_detail) {
    for (const entry of conflict.dependency_detail.ab ?? []) {
      dependencyRows.push({
        editor: a,
        consumer: b,
        file: entry.file,
        symbols: entry.symbols,
      });
    }
    for (const entry of conflict.dependency_detail.ba ?? []) {
      dependencyRows.push({
        editor: b,
        consumer: a,
        file: entry.file,
        symbols: entry.symbols,
      });
    }
  }

  return (
    <div className="bg-[#f8514910] border border-[#f8514930] rounded-lg p-2.5 mb-2">
      <div className="flex items-center gap-1.5 mb-1.5">
        <AlertTriangle className="size-3.5 text-[var(--red)]" />
        <span className="text-xs font-medium text-[var(--red)]">
          {categoryLabel}
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
      {dependencyRows.length > 0 && (
        <div className="text-[11px] text-[var(--text-secondary)] mb-2 space-y-1">
          {dependencyRows.map((row, i) => (
            <div key={i} className="leading-tight">
              <span className="font-medium text-[var(--text-primary)]">
                {row.editor}
              </span>
              {" "}
              {row.symbols && row.symbols.length > 0 ? (
                <>
                  is changing{" "}
                  {row.symbols.map((s, j) => (
                    <span key={s}>
                      <code className="px-1 py-0.5 bg-[var(--bg-tertiary)] rounded text-[10px] text-[var(--text-primary)]">
                        {s}
                      </code>
                      {j < row.symbols!.length - 1 ? ", " : ""}
                    </span>
                  ))}
                </>
              ) : (
                <>is editing a file imported by</>
              )}
              {" "}
              <span className="text-[var(--text-secondary)]">
                — affects{" "}
                <span className="font-medium text-[var(--text-primary)]">
                  {row.consumer}
                </span>
                &rsquo;s{" "}
                <code className="px-1 py-0.5 bg-[var(--bg-tertiary)] rounded text-[10px] text-[var(--text-primary)]">
                  {row.file}
                </code>
              </span>
            </div>
          ))}
        </div>
      )}
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
  /** True when the API returned 402 Payment Required — i.e. this user
   * hasn't added a BYOK Anthropic key yet. We render a link to /settings. */
  needsApiKey?: boolean;
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
      const needsApiKey = err instanceof ApiError && err.status === 402;
      setTurns((prev) =>
        prev.map((t) =>
          t.id === pendingTurn.id
            ? {
                ...t,
                content: message,
                pending: false,
                error: true,
                needsApiKey,
              }
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
                  <>
                    {t.content.split("\n").map((line, i) => (
                      <p key={i} className={line === "" ? "h-2" : "mb-0.5 whitespace-pre-wrap break-words"}>
                        {line}
                      </p>
                    ))}
                    {t.needsApiKey && (
                      <Link
                        href="/settings"
                        className="inline-block mt-2 text-[11px] px-2 py-1 rounded bg-[var(--accent)]/10 text-[var(--accent)] ring-1 ring-[var(--accent)]/30 hover:bg-[var(--accent)]/20 transition-colors"
                      >
                        Add API key in Settings →
                      </Link>
                    )}
                  </>
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
  const [showNewFile, setShowNewFile] = useState(false);
  // Pre-filled path for the NewFileModal when summoned from a right-click
  // on a folder row (e.g. ``pkg/``). Empty = user opened with the "+" or
  // right-clicked empty space.
  const [newFilePrefix, setNewFilePrefix] = useState("");
  const [showConnectClaude, setShowConnectClaude] = useState(false);

  // Files-panel right-click context menu. ``target`` is the path of the
  // row right-clicked (file or folder); undefined means the user right-
  // clicked empty scroll area. Kept at ProjectPage level so the menu
  // survives re-renders of the tree.
  const [fileCtxMenu, setFileCtxMenu] = useState<
    { x: number; y: number; target?: string; isFolder?: boolean } | null
  >(null);
  // In-page destructive confirm (replaces window.confirm — see
  // destructive-confirm-modal.tsx for why a real modal over native dialog).
  const [pendingDanger, setPendingDanger] = useState<"delete" | "leave" | null>(null);
  const [dangerBusy, setDangerBusy] = useState(false);
  const [agentConnected, setAgentConnected] = useState(false);
  const [activePath, setActivePath] = useState<string | null>(null);

  // File state — list of paths is authoritative; contents cached per-path as
  // they're opened. A null content entry means "not loaded yet".
  const [filePaths, setFilePaths] = useState<string[]>([]);
  const [fileContents, setFileContents] = useState<Record<string, string>>({});
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
        const [p, t, files] = await Promise.all([
          api.getProject(projectId),
          api.getMpacToken(projectId),
          api.listProjectFiles(projectId),
        ]);
        if (cancelled) return;
        setProject(p);
        setMpacToken(t);
        const paths = files.files.map((f) => f.path);
        setFilePaths(paths);
        // Auto-open the first file so the editor isn't blank on arrival.
        if (paths.length > 0) setActivePath(paths[0]);
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

  // Poll agent relay status every 5s so the header badge reflects whether
  // the user's local Claude Code is connected. Cheap HTTP call, no WS needed.
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const s = await api.getAgentStatus(projectId);
        if (!cancelled) setAgentConnected(s.connected);
      } catch {
        /* user might not yet be a member; silent */
      }
    };
    tick();
    const interval = setInterval(tick, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [user, projectId]);

  // Lazy-load the content of whichever file is active. We cache in
  // fileContents so switching back to an already-opened file is instant.
  useEffect(() => {
    if (!activePath) return;
    if (activePath in fileContents) return;
    let cancelled = false;
    (async () => {
      try {
        const f = await api.readProjectFile(projectId, activePath);
        if (cancelled) return;
        setFileContents((prev) => ({ ...prev, [activePath]: f.content }));
      } catch (e) {
        if (cancelled) return;
        console.error("Failed to load file", activePath, e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activePath, fileContents, projectId]);

  // Debounced autosave — queued on every keystroke, only the last fires.
  const scheduleSave = (path: string, content: string) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    setSaveStatus("saving");
    saveTimerRef.current = setTimeout(async () => {
      try {
        await api.writeProjectFile(projectId, path, content);
        setSaveStatus("saved");
      } catch (e) {
        console.error("Save failed", e);
        setSaveStatus("error");
      }
    }, 800);
  };

  const handleEditorChange = (value: string | undefined) => {
    if (!activePath) return;
    const next = value ?? "";
    setFileContents((prev) => ({ ...prev, [activePath]: next }));
    scheduleSave(activePath, next);
  };

  const handleCreateFile = async (path: string) => {
    // Called by NewFileModal after basic client-side validation. The modal
    // stays open (showing the error) if this throws.
    try {
      await api.writeProjectFile(projectId, path, "");
      setFilePaths((prev) => [...prev, path].sort());
      setFileContents((prev) => ({ ...prev, [path]: "" }));
      setActivePath(path);
    } catch (e) {
      throw new Error(
        e instanceof ApiError ? e.message : "Failed to create file",
      );
    }
  };

  const handleDeleteFile = async (path: string) => {
    if (!window.confirm(`Delete ${path}?`)) return;
    try {
      await api.deleteProjectFile(projectId, path);
      setFilePaths((prev) => prev.filter((p) => p !== path));
      setFileContents((prev) => {
        const next = { ...prev };
        delete next[path];
        return next;
      });
      if (activePath === path) {
        // Pick a sibling to open next, or clear if the tree is empty.
        const remaining = filePaths.filter((p) => p !== path);
        setActivePath(remaining[0] ?? null);
      }
    } catch (e) {
      window.alert(
        `Delete failed: ${e instanceof ApiError ? e.message : "unknown error"}`,
      );
    }
  };

  // Derived file tree for the sidebar + command palette.
  const fileTree = buildFileTree(filePaths);

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
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setShowConnectClaude(true)}
            className={
              agentConnected
                ? "gap-1.5 text-[#3fb950] hover:text-[#3fb950] border border-[#3fb950]/30"
                : "gap-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)]"
            }
            title={
              agentConnected
                ? "Your local Claude Code is bridged into this project"
                : "Bridge your local Claude Code subscription (no API key needed)"
            }
          >
            <Bot className="size-3.5" />
            {agentConnected ? "Claude connected" : "Connect Claude"}
          </Button>
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
          {isOwner ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setPendingDanger("delete")}
              title="Delete this project for everyone (owner only)"
              className="gap-1.5 text-[var(--red)] hover:bg-[var(--red)]/15 border border-transparent hover:border-[var(--red)]/40"
            >
              <Trash2 className="size-3.5" />
              Delete
            </Button>
          ) : (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setPendingDanger("leave")}
              title="Remove yourself from this project"
              className="gap-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-transparent hover:border-[var(--border)]"
            >
              <LogOut className="size-3.5" />
              Leave
            </Button>
          )}
          <Link
            href="/settings"
            className="text-xs px-2 py-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            Settings
          </Link>
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
          <div className="px-3 py-2 border-b border-[var(--border)] flex items-center justify-between">
            <span className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
              Files
            </span>
            <button
              type="button"
              onClick={() => setShowNewFile(true)}
              className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-base leading-none"
              title="New file"
              aria-label="New file"
            >
              +
            </button>
          </div>
          <div
            className="flex-1 overflow-y-auto py-1"
            // Right-click ANYWHERE in the scroll area — including empty
            // space below the tree — opens a context menu with "New
            // file". Row-level handlers (in FileTree) stopPropagation
            // so right-clicking a row targets that specific file, not
            // this empty-area handler.
            onContextMenu={(e) => {
              e.preventDefault();
              setFileCtxMenu({ x: e.clientX, y: e.clientY });
            }}
          >
            {filePaths.length === 0 ? (
              <div className="px-3 py-3 text-[11px] text-[var(--text-secondary)]">
                No files yet. Click <span className="text-[var(--text-primary)]">+</span>
                {" "}or right-click here to add one.
              </div>
            ) : (
              <FileTree
                files={fileTree}
                activePath={activePath}
                participants={session.participants}
                selfPrincipalId={selfPrincipalId}
                myIntents={session.myIntents}
                onSelect={setActivePath}
                onDelete={handleDeleteFile}
                onContextMenu={(e, path, isFolder) => {
                  setFileCtxMenu({
                    x: e.clientX,
                    y: e.clientY,
                    target: path,
                    isFolder,
                  });
                }}
              />
            )}
          </div>
        </Panel>

        <VSplit />

        {/* Center: editor */}
        <Panel id="editor" defaultSize="60%" minSize="25%"
               className="flex flex-col bg-[var(--bg-primary)]">
          <div className="h-9 bg-[var(--bg-secondary)] border-b border-[var(--border)] flex items-center px-2 gap-2 flex-shrink-0">
            <div className="flex items-center gap-1.5 px-3 py-1 bg-[var(--bg-primary)] rounded-t border border-[var(--border)] border-b-transparent text-xs">
              <span className="text-[#e6edf3]">{activePath ?? "(no file)"}</span>
            </div>
            {activePath && (
              <span className="text-[11px] text-[var(--text-secondary)] ml-auto pr-2" title="Autosave state">
                {saveStatus === "saving" && "Saving…"}
                {saveStatus === "saved" && "Saved"}
                {saveStatus === "error" && (
                  <span className="text-[var(--red)]">Save failed</span>
                )}
              </span>
            )}
          </div>
          <div className="flex-1 min-h-0">
            <Editor
              height="100%"
              language={activePath ? languageForPath(activePath) : "plaintext"}
              theme="vs-dark"
              path={activePath ?? "untitled"}
              value={activePath ? (fileContents[activePath] ?? "") : ""}
              onChange={handleEditorChange}
              onMount={(editor) => {
                // Kick a manual layout after paint — some browser/host combos
                // (embedded Playwright, for one) don't fire the ResizeObserver
                // on initial mount, leaving the editor stuck at 5×5.
                setTimeout(() => editor.layout(), 0);
              }}
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

      <NewFileModal
        open={showNewFile}
        onOpenChange={(o) => {
          setShowNewFile(o);
          // When the modal closes, clear any right-click-derived prefix
          // so the next "+" click opens with a blank input, not the
          // leftover folder name from the last context-menu invocation.
          if (!o) setNewFilePrefix("");
        }}
        existingPaths={filePaths}
        onCreate={handleCreateFile}
        initialPath={newFilePrefix}
      />

      {/*
        Right-click menu for the Files panel. Items depend on what was
        clicked: empty area gets just "New file"; a file row adds
        "Delete"; a folder row pre-fills the new-file dialog with the
        folder's path so typing a filename completes the path in one
        breath (``pkg/`` + user types ``foo.py`` → pkg/foo.py).
      */}
      {fileCtxMenu && (
        <FileContextMenu
          x={fileCtxMenu.x}
          y={fileCtxMenu.y}
          onClose={() => setFileCtxMenu(null)}
          items={
            ((): FileContextMenuItem[] => {
              const items: FileContextMenuItem[] = [];
              const target = fileCtxMenu.target;
              const isFolder = fileCtxMenu.isFolder;
              items.push({
                label: isFolder && target
                  ? `New file in ${target}/`
                  : "New file",
                onSelect: () => {
                  setNewFilePrefix(isFolder && target ? `${target}/` : "");
                  setShowNewFile(true);
                },
              });
              if (target && !isFolder) {
                items.push({
                  label: `Delete ${target.split("/").pop()}`,
                  destructive: true,
                  onSelect: () => handleDeleteFile(target),
                });
              }
              return items;
            })()
          }
        />
      )}

      <ConnectClaudeModal
        projectId={projectId}
        open={showConnectClaude}
        onOpenChange={setShowConnectClaude}
      />

      <DestructiveConfirmModal
        open={pendingDanger !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDanger(null);
        }}
        title={
          pendingDanger === "delete"
            ? `Delete project "${project.name}"?`
            : pendingDanger === "leave"
              ? `Leave "${project.name}"?`
              : ""
        }
        body={
          pendingDanger === "delete"
            ? "This permanently removes all files, invites, and tokens.\n\n" +
              "Every member (including Claude agents) loses access immediately.\n\n" +
              "This can't be undone."
            : pendingDanger === "leave"
              ? "Your browser session and any Claude relay you have running will lose access.\n\n" +
                "The project stays put for the owner and other members — they can re-invite you later if needed."
              : ""
        }
        confirmLabel={pendingDanger === "delete" ? "Delete" : "Leave"}
        busy={dangerBusy}
        onConfirm={async () => {
          if (!pendingDanger) return;
          setDangerBusy(true);
          try {
            if (pendingDanger === "delete") {
              await api.deleteProject(project.id);
            } else {
              await api.leaveProject(project.id);
            }
            // Regardless of action, user no longer has access → dashboard.
            router.push("/projects");
          } catch (e) {
            setLoadError(
              e instanceof ApiError
                ? `${pendingDanger === "delete" ? "Delete" : "Leave"} failed: ${e.message}`
                : `${pendingDanger === "delete" ? "Delete" : "Leave"} failed — see console.`
            );
            setPendingDanger(null);
            // eslint-disable-next-line no-console
            console.error(e);
          } finally {
            setDangerBusy(false);
          }
        }}
      />

      <CommandPalette
        open={showPalette}
        onOpenChange={setShowPalette}
        files={fileTree}
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
