"use client";
// "Connect Claude" modal — mints an agent bearer token and shows a
// copy-paste command the user runs locally to start `mpac-mcp-relay`.
// Polls agent-status every 2s until the relay actually connects so the
// user gets immediate visual confirmation.

import { useEffect, useRef, useState } from "react";
import { Copy, Check, Bot, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { AgentTokenResponse } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";

export function ConnectClaudeModal({
  projectId,
  open,
  onOpenChange,
}: {
  projectId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [agentToken, setAgentToken] = useState<AgentTokenResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [connected, setConnected] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Which OS / shell the user wants the command for. Default tries to
  // infer from the browser's userAgent on first mount (Windows →
  // "windows"; else "unix") then respects the user's explicit choice
  // which we persist across modal open/close via localStorage so a
  // Windows user doesn't have to toggle every time.
  const [osTab, setOsTab] = useState<"unix" | "windows">(() => {
    if (typeof window === "undefined") return "unix";
    const saved = window.localStorage.getItem("mpac.connectClaudeOs");
    if (saved === "unix" || saved === "windows") return saved;
    const ua = window.navigator.userAgent || "";
    return /Windows/i.test(ua) ? "windows" : "unix";
  });
  // Persist tab choice so repeat opens remember it.
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("mpac.connectClaudeOs", osTab);
  }, [osTab]);

  // Generate the token as soon as the modal opens.
  useEffect(() => {
    if (!open) {
      // Reset on close so a reopened modal doesn't flash the stale token.
      setAgentToken(null);
      setErr(null);
      setCopied(false);
      setConnected(false);
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      return;
    }
    (async () => {
      setErr(null);
      setBusy(true);
      try {
        const tok = await api.mintAgentToken(projectId);
        setAgentToken(tok);
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : "Failed to mint token");
      } finally {
        setBusy(false);
      }
    })();
  }, [open, projectId]);

  // Poll agent-status every 2s while the modal is open and we have a token.
  // Stops as soon as the relay reports connected.
  useEffect(() => {
    if (!open || !agentToken || connected) return;
    const tick = async () => {
      try {
        const s = await api.getAgentStatus(projectId);
        if (s.connected) {
          setConnected(true);
          if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }
        }
      } catch {
        /* transient; keep polling */
      }
    };
    tick(); // immediate first poll
    pollTimerRef.current = setInterval(tick, 2000);
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [open, agentToken, connected, projectId]);

  async function onCopy() {
    if (!agentToken) return;
    try {
      await navigator.clipboard.writeText(activeCommand);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable — user can still select manually */
    }
  }

  // Pick the command for the active OS tab. Fallback to the unix form
  // when the server didn't send the Windows variant (older backend).
  const activeCommand = agentToken
    ? (osTab === "windows" && agentToken.launch_command_windows
        ? agentToken.launch_command_windows
        : agentToken.launch_command)
    : "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[var(--bg-secondary)] border-[var(--border)] text-[var(--text-primary)] sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="text-[#e6edf3] flex items-center gap-2">
            <Bot className="size-5 text-[#58a6ff]" />
            Connect Claude Code
          </DialogTitle>
          <DialogDescription className="text-[var(--text-secondary)]">
            Bridge your local Claude Code subscription into this project.
            No API key needed — uses your existing Claude Pro / Max login.
          </DialogDescription>
        </DialogHeader>

        {err && (
          <Alert variant="destructive">
            <AlertDescription>{err}</AlertDescription>
          </Alert>
        )}

        {busy && !agentToken && (
          <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <Loader2 className="size-4 animate-spin" />
            Generating bearer token…
          </div>
        )}

        {agentToken && (
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
                <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide">
                  Run this on your laptop
                </label>
                {/*
                  OS segmented control. Two flat pills; active one gets the
                  accent background. Kept unobtrusive: the whole widget sits
                  inline with the label so it doesn't look like another
                  section. Only shown when the server actually sent a
                  Windows variant; older backends degrade gracefully (no
                  toggle = one bash command, same as before).
                */}
                {agentToken.launch_command_windows && (
                  <div
                    className="inline-flex rounded-md border border-[var(--border)] bg-[var(--bg-tertiary)] p-0.5 text-[11px]"
                    role="tablist"
                    aria-label="Operating system"
                  >
                    <button
                      type="button"
                      role="tab"
                      aria-selected={osTab === "unix"}
                      onClick={() => setOsTab("unix")}
                      className={
                        "px-2 py-0.5 rounded transition-colors " +
                        (osTab === "unix"
                          ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]")
                      }
                    >
                      macOS / Linux
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={osTab === "windows"}
                      onClick={() => setOsTab("windows")}
                      className={
                        "px-2 py-0.5 rounded transition-colors " +
                        (osTab === "windows"
                          ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]")
                      }
                    >
                      Windows
                    </button>
                  </div>
                )}
              </div>
              <div className="relative">
                {/*
                  Visual wrap on long commands (the curl URL + token is ~160
                  chars and blew past the modal before). Using
                  ``whitespace-pre-wrap`` + ``break-all`` wraps anywhere a
                  break is needed — but because the clipboard write pulls
                  from ``agentToken.launch_command`` directly, the copied
                  text is still the pristine single-line command (verified
                  manually: the DOM has no inserted whitespace, it's just
                  a CSS rendering hint).

                  ``pr-20`` reserves space so the absolutely-positioned
                  Copy button never sits on top of the command text, even
                  on the very first (top) line.
                */}
                <pre className="rounded-md border border-[var(--border)] bg-[var(--bg-tertiary)] p-3 pr-20 text-xs font-mono leading-relaxed whitespace-pre-wrap break-all text-[var(--text-primary)]">
{activeCommand}
                </pre>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={onCopy}
                  className="absolute top-2 right-2 h-7 px-2"
                >
                  {copied ? (
                    <>
                      <Check className="size-3.5" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="size-3.5" />
                      Copy
                    </>
                  )}
                </Button>
              </div>
              <p className="text-[11px] text-[var(--text-secondary)] mt-2">
                {osTab === "windows" ? (
                  <>
                    Run in <strong>PowerShell</strong>. Needs{" "}
                    <code className="font-mono">node</code> and{" "}
                    <code className="font-mono">python</code> on your
                    machine.
                  </>
                ) : (
                  <>
                    Run in any <strong>bash</strong>-compatible shell
                    (macOS Terminal, Linux, WSL, Git Bash). Needs{" "}
                    <code className="font-mono">node</code> +{" "}
                    <code className="font-mono">python3</code> on your
                    laptop.
                  </>
                )}{" "}
                The rest (
                <a
                  href="https://docs.anthropic.com/en/docs/claude-code/setup"
                  target="_blank"
                  rel="noreferrer"
                  className="underline hover:text-[var(--text-primary)]"
                >
                  Claude Code
                </a>
                , <code className="font-mono">mpac-mcp</code>, and a
                one-time <code className="font-mono">claude /login</code>
                browser flow) auto-installs from the command above. Token
                is single-use — if the script fails, reopen this modal.
              </p>
            </div>

            <div className="rounded-md border border-[var(--border)] p-3 bg-[var(--bg-primary)]">
              <div className="flex items-center gap-2 text-sm">
                {connected ? (
                  <>
                    <span className="inline-block size-2 rounded-full bg-[#3fb950]" />
                    <span className="text-[#3fb950] font-medium">
                      Connected
                    </span>
                    <span className="text-[var(--text-secondary)]">
                      — Claude will appear in the &quot;Who&apos;s working&quot; panel.
                    </span>
                  </>
                ) : (
                  <>
                    <Loader2 className="size-3.5 animate-spin text-[var(--text-secondary)]" />
                    <span className="text-[var(--text-secondary)]">
                      Waiting for the relay to connect…
                    </span>
                  </>
                )}
              </div>
              {connected && (
                <p className="text-[11px] text-[var(--text-secondary)] mt-2">
                  Leave the relay running in the background; closing it will
                  disconnect your Claude from the session.
                </p>
              )}
            </div>

            <p className="text-[11px] text-[var(--text-secondary)]">
              Token is one-time: running this endpoint again revokes the
              previous token and issues a new one.
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
