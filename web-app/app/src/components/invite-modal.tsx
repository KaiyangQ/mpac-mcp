"use client";
// Owner-only invite modal. Generates an invite link the owner can share.

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { greenBtnClass } from "@/components/auth-shell";

export function InviteModal({
  projectId,
  projectName,
  open,
  onOpenChange,
}: {
  projectId: number;
  projectName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
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
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          // Reset form state when the dialog closes so a reopened instance
          // doesn't show a stale link or error.
          setLink(null);
          setErr(null);
          setCopied(false);
        }
        onOpenChange(next);
      }}
    >
      <DialogContent className="bg-[var(--bg-secondary)] border-[var(--border)] text-[var(--text-primary)] sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-[#e6edf3]">Invite to {projectName}</DialogTitle>
          <DialogDescription className="text-[var(--text-secondary)]">
            Generate a one-time link your collaborator can use to join.
          </DialogDescription>
        </DialogHeader>

        {err && (
          <Alert variant="destructive">
            <AlertDescription>{err}</AlertDescription>
          </Alert>
        )}

        {!link ? (
          <Button onClick={onGenerate} disabled={busy} className={greenBtnClass}>
            {busy ? "Generating…" : "Generate invite link"}
          </Button>
        ) : (
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide mb-2">
              Share this link
            </label>
            <div className="flex gap-2">
              <Input
                readOnly
                value={link}
                onClick={(e) => e.currentTarget.select()}
                className="font-mono text-xs"
              />
              <Button
                type="button"
                variant="secondary"
                onClick={onCopy}
                className="shrink-0"
              >
                {copied ? (
                  <>
                    <Check className="size-4" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="size-4" />
                    Copy
                  </>
                )}
              </Button>
            </div>
            <p className="text-[11px] text-[var(--text-secondary)] mt-3">
              The link is single-use. Once accepted, generate a new one to
              invite another person.
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
