"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, api, type AnthropicKeyStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { TopNav } from "@/components/top-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { labelClass } from "@/components/auth-shell";

export default function SettingsPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  const [status, setStatus] = useState<AnthropicKeyStatus | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Redirect unauthenticated users to /login. We gate on isLoading so we
  // don't bounce users who are still in the bootstrap phase.
  useEffect(() => {
    if (!isLoading && !user) router.replace("/login?next=/settings");
  }, [isLoading, user, router]);

  const refresh = useCallback(async () => {
    try {
      const s = await api.getAnthropicKey();
      setStatus(s);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Failed to load settings");
    }
  }, []);

  useEffect(() => {
    if (user) refresh();
  }, [user, refresh]);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setSaved(false);
    setBusy(true);
    try {
      const s = await api.setAnthropicKey(input.trim());
      setStatus(s);
      setInput("");
      setSaved(true);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Failed to save key");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!confirm("Remove your Anthropic API key? The AI chat will stop working until you add a new one.")) {
      return;
    }
    setErr(null);
    setSaved(false);
    setBusy(true);
    try {
      const s = await api.deleteAnthropicKey();
      setStatus(s);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Failed to delete key");
    } finally {
      setBusy(false);
    }
  }

  if (isLoading || !user) {
    return (
      <div className="h-screen flex flex-col bg-[var(--bg-primary)]">
        <TopNav title="Settings" />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-[var(--bg-primary)]">
      <TopNav title="Settings" />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-6 py-8 space-y-8">
          <section>
            <h2 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider mb-2">
              Anthropic API key (BYOK)
            </h2>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-4">
              The AI chat runs on your own Anthropic API key — we never share
              one across users, and MPAC never sees the plaintext key again
              after you save it (it&apos;s encrypted in our database).{" "}
              <a
                href="https://console.anthropic.com/settings/keys"
                target="_blank"
                rel="noreferrer"
                className="text-[var(--accent)] hover:underline"
              >
                Grab a key from console.anthropic.com →
              </a>
            </p>

            <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-5">
              {status?.has_key ? (
                <div className="mb-4 text-sm text-[var(--text-primary)]">
                  <span className="text-[var(--text-secondary)]">On file: </span>
                  <code className="font-mono bg-[var(--bg-tertiary)] px-1.5 py-0.5 rounded text-xs">
                    {status.key_preview || "••••••••"}
                  </code>
                </div>
              ) : (
                <div className="mb-4 text-sm text-[var(--red)]">
                  No API key on file — the AI chat is disabled for your account.
                </div>
              )}

              {err && (
                <Alert variant="destructive" className="mb-3">
                  <AlertDescription>{err}</AlertDescription>
                </Alert>
              )}
              {saved && !err && (
                <Alert className="mb-3">
                  <AlertDescription>Saved. You can now chat with Claude.</AlertDescription>
                </Alert>
              )}

              <form onSubmit={onSave} className="space-y-3">
                <div>
                  <label className={labelClass}>
                    {status?.has_key ? "Replace API key" : "API key"}
                  </label>
                  <Input
                    type="password"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="sk-ant-api03-…"
                    autoComplete="off"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    type="submit"
                    disabled={busy || !input.trim()}
                    className="bg-[#238636] hover:bg-[#2ea043] text-white disabled:bg-[#238636]/50"
                  >
                    {busy ? "Saving…" : status?.has_key ? "Update key" : "Save key"}
                  </Button>
                  {status?.has_key && (
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={onDelete}
                      disabled={busy}
                      className="text-[var(--red)] hover:text-[var(--red)] hover:bg-[var(--red)]/10"
                    >
                      Remove key
                    </Button>
                  )}
                </div>
              </form>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-[var(--text-primary)] uppercase tracking-wider mb-2">
              Account
            </h2>
            <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-5 text-sm text-[var(--text-primary)] space-y-1">
              <div>
                <span className="text-[var(--text-secondary)]">Display name: </span>
                {user.display_name}
              </div>
              <div>
                <span className="text-[var(--text-secondary)]">Email: </span>
                {user.email}
              </div>
            </div>
          </section>

          <div className="pt-2">
            <Link
              href="/projects"
              className="text-xs text-[var(--text-secondary)] hover:text-[var(--accent)]"
            >
              ← Back to projects
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
