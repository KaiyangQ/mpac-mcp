"use client";

import { useState } from "react";
import dynamic from "next/dynamic";

// Monaco must be loaded client-side only (no SSR)
const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

// ── Mock Data ─────────────────────────────────────────────

type FileNode = { name: string; children?: FileNode[]; active?: boolean; editedBy?: string };

const MOCK_FILES: FileNode[] = [
  { name: "src/", children: [
    { name: "auth.py", active: true },
    { name: "api.py", editedBy: "Alice" },
    { name: "utils/", children: [
      { name: "helpers.py", editedBy: "Claude" },
      { name: "validators.py" },
    ]},
  ]},
  { name: "tests/", children: [
    { name: "test_auth.py" },
    { name: "test_api.py" },
  ]},
  { name: "README.md" },
];

const MOCK_CODE = `from flask import Flask, request, jsonify
from flask_login import login_required
import jwt

def verify_token(token: str) -> dict | None:
    """Verify a JWT and return the claims."""
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def login_required_api(f):
    """Decorator for API endpoints that require authentication."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return jsonify({"error": "Missing token"}), 401
        claims = verify_token(token)
        if not claims:
            return jsonify({"error": "Invalid token"}), 401
        request.user = claims
        return f(*args, **kwargs)
    return decorated
`;

const MOCK_PARTICIPANTS = [
  { name: "Kaiyang", status: "working", file: "auth.py", intent: "fixing login bug", online: true, isYou: true, isAI: false },
  { name: "Claude", status: "working", file: "utils/helpers.py", intent: "refactoring helper functions", online: true, isYou: false, isAI: true },
  { name: "Alice", status: "idle", file: "api.py", intent: "adding REST endpoints", online: true, isYou: false, isAI: false },
  { name: "Bob", status: "offline", file: null, intent: null, online: false, isYou: false, isAI: false },
];

const MOCK_CONFLICTS = [
  { id: "c1", file: "auth.py", principalA: "Kaiyang", principalB: "Claude", category: "scope_overlap" },
];

const MOCK_CHAT = [
  { role: "user" as const, content: "帮我重构 auth.py 的 verify_token 函数，加上 refresh token 支持" },
  { role: "assistant" as const, content: "好的，我来分析一下当前的 verify_token 实现。我会：\n\n1. 添加 refresh token 的验证逻辑\n2. 分离 access token 和 refresh token 的处理\n3. 添加 token rotation 机制\n\n正在修改 auth.py..." },
];

// ── Components ────────────────────────────────────────────

function FileTree({ files, depth = 0 }: { files: FileNode[]; depth?: number }) {
  return (
    <div>
      {files.map((f) => (
        <div key={f.name}>
          <div
            className={`flex items-center gap-1.5 py-1 text-[13px] cursor-pointer hover:bg-[var(--bg-tertiary)] rounded transition-colors ${
              f.active ? "bg-[var(--bg-tertiary)] text-[var(--accent)]" : "text-[var(--text-primary)]"
            }`}
            style={{ paddingLeft: `${depth * 16 + 12}px`, paddingRight: "8px" }}
          >
            <span className="text-[var(--text-secondary)] text-xs">
              {f.children ? "📁" : "📄"}
            </span>
            <span className="flex-1">{f.name}</span>
            {f.active && (
              <span className="w-2 h-2 rounded-full bg-[var(--accent)]" title="You are editing" />
            )}
            {f.editedBy && !f.active && (
              <span className="w-2 h-2 rounded-full bg-[var(--green)]" title={`${f.editedBy} is editing`} />
            )}
          </div>
          {f.children && <FileTree files={f.children} depth={depth + 1} />}
        </div>
      ))}
    </div>
  );
}

function CollabPanel() {
  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Participants */}
      <div className="p-3 border-b border-[var(--border)]">
        <h3 className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2.5">
          Who&apos;s Working
        </h3>
        <div className="space-y-2.5">
          {MOCK_PARTICIPANTS.map((p) => (
            <div key={p.name} className="flex items-start gap-2.5">
              <div className="relative mt-0.5 flex-shrink-0">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium ${
                  p.isAI ? "bg-[#1f2937] text-[var(--accent)] ring-1 ring-[var(--accent)]/30" : "bg-[var(--bg-tertiary)] text-[var(--text-primary)]"
                }`}>
                  {p.isAI ? "🤖" : p.name[0]}
                </div>
                <span className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-[var(--bg-secondary)] ${
                  p.online ? "bg-[var(--green)]" : "bg-[#484f58]"
                }`} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium truncate">{p.name}</span>
                  {p.isYou && <span className="text-[10px] text-[var(--text-secondary)]">(you)</span>}
                  {p.isAI && <span className="text-[9px] px-1 py-px bg-[#1f2937] text-[var(--accent)] rounded">AI</span>}
                </div>
                {p.file ? (
                  <div className="text-xs text-[var(--text-secondary)] truncate mt-0.5">
                    📝 {p.file}
                  </div>
                ) : !p.online ? (
                  <div className="text-xs text-[#484f58] mt-0.5">offline</div>
                ) : (
                  <div className="text-xs text-[var(--text-secondary)] mt-0.5">idle</div>
                )}
                {p.intent && (
                  <div className="text-[11px] text-[var(--accent)] truncate mt-0.5 italic">
                    &ldquo;{p.intent}&rdquo;
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Conflicts */}
      <div className="p-3">
        <h3 className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2.5">
          Conflicts
        </h3>
        {MOCK_CONFLICTS.map((c) => (
          <div key={c.id} className="bg-[#f8514910] border border-[#f8514930] rounded-lg p-2.5 mb-2">
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="text-sm">⚠️</span>
              <span className="text-xs font-medium text-[var(--red)]">Scope Overlap</span>
            </div>
            <div className="text-xs text-[var(--text-primary)] mb-2">
              <span className="font-medium">{c.principalA}</span>
              <span className="text-[var(--text-secondary)]"> ↔ </span>
              <span className="font-medium">{c.principalB}</span>
              <span className="text-[var(--text-secondary)]"> on </span>
              <span className="text-[var(--accent)]">{c.file}</span>
            </div>
            <div className="flex gap-1.5">
              <button className="text-[11px] px-2 py-1 bg-[var(--bg-tertiary)] hover:bg-[var(--border)] border border-[var(--border)] rounded text-[var(--text-primary)] transition-colors">
                Acknowledge
              </button>
              <button className="text-[11px] px-2 py-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
                View Details
              </button>
            </div>
          </div>
        ))}
        {MOCK_CONFLICTS.length === 0 && (
          <div className="text-xs text-[var(--text-secondary)] text-center py-4">
            ✅ No conflicts
          </div>
        )}
      </div>
    </div>
  );
}

function AiChat() {
  const [input, setInput] = useState("");

  return (
    <div className="flex flex-col h-full border-t border-[var(--border)]">
      <div className="px-3 py-2 border-b border-[var(--border)] flex items-center gap-2 flex-shrink-0">
        <span className="text-sm">🤖</span>
        <span className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">AI Assistant</span>
        <span className="ml-auto text-[9px] px-1.5 py-0.5 bg-[#1f2937] text-[var(--accent)] rounded-full font-medium">Claude</span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
        {MOCK_CHAT.map((msg, i) => (
          <div key={i} className="flex gap-2">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] flex-shrink-0 mt-0.5 ${
              msg.role === "user" ? "bg-[var(--bg-tertiary)] text-[var(--text-primary)] font-medium" : "bg-[#1f2937] text-[var(--accent)] ring-1 ring-[var(--accent)]/30"
            }`}>
              {msg.role === "user" ? "K" : "🤖"}
            </div>
            <div className="text-[13px] leading-relaxed text-[var(--text-primary)]">
              {msg.content.split("\n").map((line, j) => (
                <p key={j} className={line === "" ? "h-2" : "mb-0.5"}>{line}</p>
              ))}
            </div>
          </div>
        ))}
        {/* Typing indicator */}
        <div className="flex gap-2 items-center">
          <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] bg-[#1f2937] text-[var(--accent)] ring-1 ring-[var(--accent)]/30 flex-shrink-0">🤖</div>
          <div className="flex gap-1 items-center">
            <span className="w-1.5 h-1.5 bg-[var(--accent)] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="w-1.5 h-1.5 bg-[var(--accent)] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="w-1.5 h-1.5 bg-[var(--accent)] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            <span className="text-[11px] text-[var(--text-secondary)] ml-1">modifying auth.py...</span>
          </div>
        </div>
      </div>

      {/* Input */}
      <div className="p-2 border-t border-[var(--border)] flex-shrink-0">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask AI to help with your code..."
            className="flex-1 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[#484f58] focus:outline-none focus:border-[var(--accent)] transition-colors"
          />
          <button className="px-3 py-2 bg-[#238636] hover:bg-[#2ea043] text-white text-sm rounded-lg transition-colors font-medium">
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────

export default function WorkspacePage() {
  return (
    <div className="h-screen flex flex-col bg-[var(--bg-primary)]">
      {/* Top Bar */}
      <header className="h-12 bg-[var(--bg-secondary)] border-b border-[var(--border)] flex items-center px-4 gap-4 flex-shrink-0">
        <button className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
          ◀ Projects
        </button>
        <div className="h-4 w-px bg-[var(--border)]" />
        <h1 className="text-sm font-semibold text-[#e6edf3]">proj-alpha</h1>
        <div className="flex items-center gap-1 ml-2">
          {MOCK_PARTICIPANTS.filter(p => p.online).map((p) => (
            <div key={p.name} className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium border-2 border-[var(--bg-secondary)] ${
              p.isAI ? "bg-[#1f2937] text-[var(--accent)]" : "bg-[var(--bg-tertiary)] text-[var(--text-primary)]"
            }`} title={p.name}>
              {p.isAI ? "🤖" : p.name[0]}
            </div>
          ))}
          <span className="text-xs text-[var(--text-secondary)] ml-1">3 online</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button className="text-xs px-3 py-1.5 bg-[var(--bg-tertiary)] hover:bg-[var(--border)] border border-[var(--border)] rounded-md text-[var(--text-primary)] transition-colors">
            ⚙️ Settings
          </button>
          <button className="text-xs px-3 py-1.5 bg-[#238636] hover:bg-[#2ea043] rounded-md text-white transition-colors font-medium">
            📤 Invite
          </button>
        </div>
      </header>

      {/* Three-Column Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: File Tree */}
        <aside className="w-56 bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col flex-shrink-0">
          <div className="px-3 py-2 border-b border-[var(--border)]">
            <span className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Files</span>
          </div>
          <div className="flex-1 overflow-y-auto py-1">
            <FileTree files={MOCK_FILES} />
          </div>
        </aside>

        {/* Center: Monaco Editor */}
        <main className="flex-1 flex flex-col min-w-0">
          {/* Tab bar */}
          <div className="h-9 bg-[var(--bg-secondary)] border-b border-[var(--border)] flex items-center px-2 gap-0.5 flex-shrink-0">
            <div className="flex items-center gap-1.5 px-3 py-1 bg-[var(--bg-primary)] rounded-t border border-[var(--border)] border-b-transparent text-xs">
              <span className="text-[#e6edf3]">src/auth.py</span>
              <button className="text-[#484f58] hover:text-[var(--text-primary)] ml-1 transition-colors">×</button>
            </div>
          </div>
          {/* Editor */}
          <div className="flex-1">
            <Editor
              height="100%"
              language="python"
              theme="vs-dark"
              value={MOCK_CODE}
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
        </main>

        {/* Right: Collaboration + AI Chat */}
        <aside className="w-72 bg-[var(--bg-secondary)] border-l border-[var(--border)] flex flex-col flex-shrink-0">
          <div className="flex-[3] overflow-hidden">
            <CollabPanel />
          </div>
          <div className="flex-[2] flex flex-col min-h-0">
            <AiChat />
          </div>
        </aside>
      </div>

      {/* Status Bar */}
      <footer className="h-6 bg-[var(--bg-secondary)] border-t border-[var(--border)] flex items-center px-3 text-[11px] text-[var(--text-secondary)] gap-3 flex-shrink-0">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[var(--green)]" />
          Connected
        </span>
        <span className="text-[var(--border)]">|</span>
        <span>wss://mpac-demo.fly.dev/session/proj-alpha</span>
        <span className="ml-auto">contributor · Kaiyang</span>
      </footer>
    </div>
  );
}
