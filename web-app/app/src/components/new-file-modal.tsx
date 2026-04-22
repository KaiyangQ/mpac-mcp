"use client";
// Prompt the user for a new file path. Replaces the native window.prompt so
// the dialog matches the rest of the app chrome and can show inline validation.

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { greenBtnClass } from "@/components/auth-shell";

export function NewFileModal({
  open,
  onOpenChange,
  existingPaths,
  onCreate,
  initialPath,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existingPaths: string[];
  onCreate: (path: string) => Promise<void>;
  /** Pre-fill the input — used when the user right-clicks a folder so
   * the prompt opens with e.g. ``pkg/`` ready for them to type the
   * file name. Blank string = old behaviour (empty input). */
  initialPath?: string;
}) {
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Reset when reopened so a previous attempt doesn't leak through.
  // If ``initialPath`` is supplied we seed with it so the cursor lands
  // after the folder prefix ready for a file name.
  useEffect(() => {
    if (open) {
      setPath(initialPath ?? "");
      setErr(null);
      setBusy(false);
    }
  }, [open, initialPath]);

  const normalized = path.trim().replace(/^\/+/, "");
  const duplicate = normalized.length > 0 && existingPaths.includes(normalized);
  const invalid = normalized.includes("..") || normalized.includes("\\");
  const canSubmit = normalized.length > 0 && !duplicate && !invalid && !busy;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setErr(null);
    try {
      await onCreate(normalized);
      onOpenChange(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to create file");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[var(--bg-secondary)] border-[var(--border)] text-[var(--text-primary)] sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-[#e6edf3]">New file</DialogTitle>
          <DialogDescription className="text-[var(--text-secondary)]">
            Use a POSIX-style relative path. Directories are created implicitly.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label
              htmlFor="new-file-path"
              className="block text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide mb-2"
            >
              Path
            </label>
            <Input
              id="new-file-path"
              autoFocus
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="src/new_module.py"
              spellCheck={false}
              autoComplete="off"
              className="font-mono text-sm"
            />
            <p className="text-[11px] text-[var(--text-secondary)] mt-2">
              Examples: <code className="font-mono">src/api.py</code>,{" "}
              <code className="font-mono">tests/test_new.py</code>,{" "}
              <code className="font-mono">README.md</code>
            </p>
          </div>

          {duplicate && (
            <Alert variant="destructive">
              <AlertDescription>
                A file at <span className="font-mono">{normalized}</span> already
                exists.
              </AlertDescription>
            </Alert>
          )}
          {invalid && (
            <Alert variant="destructive">
              <AlertDescription>
                Path cannot contain <code className="font-mono">..</code> or
                backslashes.
              </AlertDescription>
            </Alert>
          )}
          {err && (
            <Alert variant="destructive">
              <AlertDescription>{err}</AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              onClick={() => onOpenChange(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit} className={greenBtnClass}>
              {busy ? "Creating…" : "Create file"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
