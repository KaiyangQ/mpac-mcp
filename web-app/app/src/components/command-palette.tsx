"use client";

// Workspace command palette (Cmd+K / Ctrl+K).
// MVP scope: jump to files, open invite dialog, sign out, go to projects,
// plus conditional MPAC actions (yield intent / ack conflict) when relevant.

import { useEffect, useMemo } from "react";
import {
  File as FileIcon,
  FolderOpen,
  LogOut,
  Share2,
  AlertTriangle,
  CornerUpLeft,
} from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";

type FileNode = { name: string; path: string; children?: FileNode[] };

type Intent = {
  intent_id: string;
  scope?: { resources?: string[] };
  objective?: string;
};

type Conflict = {
  conflict_id: string;
  category: string;
};

function flattenFiles(nodes: FileNode[]): { name: string; path: string }[] {
  const out: { name: string; path: string }[] = [];
  const walk = (list: FileNode[]) => {
    for (const n of list) {
      if (!n.children) out.push({ name: n.name, path: n.path });
      else walk(n.children);
    }
  };
  walk(nodes);
  return out;
}

export function CommandPalette({
  open,
  onOpenChange,
  files,
  onJumpToFile,
  onOpenInvite,
  onGotoProjects,
  onSignOut,
  myIntents,
  conflicts,
  onYieldIntent,
  onAckConflict,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  files: FileNode[];
  onJumpToFile: (path: string) => void;
  onOpenInvite?: () => void;
  onGotoProjects: () => void;
  onSignOut: () => void;
  myIntents: Record<string, Intent>;
  conflicts: Conflict[];
  onYieldIntent: (intentId: string, reason?: string) => void;
  onAckConflict: (conflictId: string) => void;
}) {
  // Cmd+K / Ctrl+K toggle. Skip when focus is in an editor / input where
  // K is a legitimate keystroke — we only intercept with the modifier.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onOpenChange]);

  const flatFiles = useMemo(() => flattenFiles(files), [files]);

  // Resolve active intents → list of "yield" actions.
  const activeIntents = useMemo(
    () => Object.values(myIntents),
    [myIntents],
  );

  const run = (fn: () => void) => {
    onOpenChange(false);
    // Defer so the dialog-close animation doesn't fight the downstream action.
    setTimeout(fn, 0);
  };

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Command palette"
      description="Search for an action or file"
      className="bg-[var(--bg-secondary)] border-[var(--border)] text-[var(--text-primary)]"
    >
      <CommandInput placeholder="Type a command or search…" />
      <CommandList>
        <CommandEmpty>No results.</CommandEmpty>

        <CommandGroup heading="Actions">
          {onOpenInvite && (
            <CommandItem
              onSelect={() => run(onOpenInvite)}
              keywords={["invite", "share", "collaborator"]}
            >
              <Share2 />
              <span>Invite collaborator</span>
            </CommandItem>
          )}
          <CommandItem
            onSelect={() => run(onGotoProjects)}
            keywords={["projects", "home", "list"]}
          >
            <FolderOpen />
            <span>Go to projects list</span>
          </CommandItem>
          <CommandItem
            onSelect={() => run(onSignOut)}
            keywords={["logout", "sign out", "exit"]}
          >
            <LogOut />
            <span>Sign out</span>
          </CommandItem>
        </CommandGroup>

        {(activeIntents.length > 0 || conflicts.length > 0) && (
          <>
            <CommandSeparator />
            <CommandGroup heading="MPAC">
              {activeIntents.map((it) => {
                const resource = it.scope?.resources?.[0] ?? "";
                return (
                  <CommandItem
                    key={`yield-${it.intent_id}`}
                    onSelect={() =>
                      run(() => onYieldIntent(it.intent_id, "palette"))
                    }
                    keywords={["yield", "withdraw", "release", resource]}
                  >
                    <CornerUpLeft />
                    <span className="truncate">
                      Yield current intent
                      {resource ? (
                        <span className="text-[var(--text-secondary)]">
                          {" "}
                          · {resource}
                        </span>
                      ) : null}
                    </span>
                  </CommandItem>
                );
              })}
              {conflicts.map((c) => (
                <CommandItem
                  key={`ack-${c.conflict_id}`}
                  onSelect={() => run(() => onAckConflict(c.conflict_id))}
                  keywords={["acknowledge", "ack", "conflict", c.category]}
                >
                  <AlertTriangle />
                  <span>
                    Acknowledge conflict
                    <span className="text-[var(--text-secondary)]">
                      {" "}
                      · {c.category}
                    </span>
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}

        <CommandSeparator />
        <CommandGroup heading="Files">
          {flatFiles.length === 0 && (
            <div className="px-2 py-3 text-xs text-[var(--text-secondary)]">
              No files
            </div>
          )}
          {flatFiles.map((f) => (
            <CommandItem
              key={f.path}
              onSelect={() => run(() => onJumpToFile(f.path))}
              keywords={["jump", "open", "file", f.name, f.path]}
            >
              <FileIcon />
              <span className="truncate">{f.path}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}

export type { FileNode };
