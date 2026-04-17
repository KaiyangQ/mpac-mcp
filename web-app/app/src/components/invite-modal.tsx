"use client";
// Owner-only invite modal. Generates an invite link the owner can share.

import { useState } from "react";
import { api, ApiError } from "@/lib/api";

export function InviteModal({
  projectId,
  projectName,
  onClose,
}: {
  projectId: number;
  projectName: string;
  onClose: () => void;
}) {
  const [link, setLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function onGenerate() {
    setErr(null);
    setBusy(true);
    try {
      const res = await api.createInvite(projectId);
      const url =
        typeof window !== "undefined"
          ? `${window.location.origin}/invite/${res.invite_code}`
          : `/invite/${res.invite_code}`;
      setLink(url);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Failed to create invite");
    } finally {
      setBusy(false);
    }
  }

  async function onCopy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable — user can still copy manually */
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4"
      onClick={onClose}
    >
      <div
        className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-6 w-full max-w-md shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-[#e6edf3]">
              Invite to {projectName}
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              Generate a one-time link your collaborator can use to join.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-lg leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {err && (
          <div className="bg-[var(--red)]/10 border border-[var(--red)]/30 text-[var(--red)] text-xs rounded-md px-3 py-2 mb-3">
            {err}
          </div>
        )}

        {!link ? (
          <button
            onClick={onGenerate}
            disabled={busy}
            className="w-full py-2 bg-[#238636] hover:bg-[#2ea043] disabled:bg-[#238636]/50 text-white text-sm font-medium rounded-md transition-colors"
          >
            {busy ? "Generating…" : "Generate invite link"}
          </button>
        ) : (
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide mb-2">
              Share this link
            </label>
            <div className="flex gap-2">
              <input
                readOnly
                value={link}
                onClick={(e) => e.currentTarget.select()}
                className="flex-1 bg-[var(--bg-primary)] border border-[var(--border)] rounded-md px-3 py-2 text-xs text-[var(--text-primary)] font-mono"
              />
              <button
                onClick={onCopy}
                className="px-3 py-2 bg-[var(--bg-tertiary)] hover:bg-[var(--border)] border border-[var(--border)] text-[var(--text-primary)] text-xs rounded-md transition-colors flex-shrink-0"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
            <p className="text-[11px] text-[var(--text-secondary)] mt-3">
              The link is single-use. Once accepted, generate a new one to
              invite another person.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
