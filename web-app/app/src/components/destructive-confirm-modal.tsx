"use client";

/**
 * In-page confirm dialog for destructive actions.
 *
 * We avoid ``window.confirm()`` because browsers (Chrome in particular)
 * increasingly suppress native JS dialogs — after a user dismisses "allow
 * this page to make dialogs" even once, every subsequent confirm returns
 * false silently. A real modal is also easier to style and A11y-audit.
 *
 * Kept deliberately minimal: title, a body the caller fully controls
 * (so it can name the specific consequence — "X files deleted, Y members
 * kicked", not "are you sure?"), a red confirm button, and a neutral
 * cancel. ``busy`` gates both buttons so a double-click can't fire the
 * API twice during the in-flight window.
 */

import { AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export function DestructiveConfirmModal({
  open,
  onOpenChange,
  title,
  body,
  confirmLabel = "Delete",
  onConfirm,
  busy = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Multi-line text; newlines render as paragraph breaks. */
  body: string;
  confirmLabel?: string;
  /** Called when the user clicks the destructive button. The parent is
   * expected to set busy=true while the async action runs, then close
   * the modal on success / leave it open + reset busy on failure. */
  onConfirm: () => void;
  busy?: boolean;
}) {
  // Split body on blank lines so each paragraph gets its own <p>. This
  // keeps the caller's text structured without asking them to pass JSX.
  const paragraphs = body.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);

  return (
    <Dialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-[#e6edf3]">
            <AlertTriangle className="size-4 text-[var(--red)]" />
            {title}
          </DialogTitle>
          <DialogDescription asChild>
            <div className="space-y-2 text-[var(--text-secondary)]">
              {paragraphs.map((p, i) => (
                <p key={i} className="text-sm leading-relaxed">
                  {p}
                </p>
              ))}
            </div>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="bg-[var(--red)] hover:bg-[var(--red)]/90 text-white border border-[var(--red)]/60"
          >
            {busy ? "Working…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
