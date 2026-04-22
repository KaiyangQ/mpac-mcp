"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Folder, LogOut, Trash2 } from "lucide-react";
import { api, ApiError, type Project } from "@/lib/api";
import { useRequireAuth } from "@/lib/redirect-hooks";
import { TopNav } from "@/components/top-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { greenBtnClass } from "@/components/auth-shell";
import { DestructiveConfirmModal } from "@/components/destructive-confirm-modal";

export default function ProjectsPage() {
  const { user, isLoading: authLoading } = useRequireAuth("/projects");
  const router = useRouter();

  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  // In-page destructive confirm — replaces window.confirm, which Chrome
  // suppresses once a user opts out of this page's dialogs.
  const [pendingAction, setPendingAction] = useState<
    | { kind: "delete" | "leave"; project: Project }
    | null
  >(null);
  const [actionBusy, setActionBusy] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setListError(null);
    try {
      const res = await api.listProjects();
      setProjects(res.projects);
    } catch (e) {
      setListError(e instanceof ApiError ? e.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) refresh();
  }, [user, refresh]);

  async function runPendingAction() {
    if (!pendingAction) return;
    const { kind, project } = pendingAction;
    setActionBusy(true);
    try {
      if (kind === "delete") {
        await api.deleteProject(project.id);
      } else {
        await api.leaveProject(project.id);
      }
      // Optimistic local removal so the list updates before the refresh
      // round-trip completes — feels snappier and avoids a flash of the
      // now-gone project while the network call resolves.
      setProjects((prev) => prev.filter((x) => x.id !== project.id));
      setPendingAction(null);
      refresh();
    } catch (e) {
      setListError(
        e instanceof ApiError
          ? `${kind === "delete" ? "Delete" : "Leave"} failed: ${e.message}`
          : `${kind === "delete" ? "Delete" : "Leave"} failed — see console.`
      );
      setPendingAction(null);
      // eslint-disable-next-line no-console
      console.error(e);
    } finally {
      setActionBusy(false);
    }
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const p = await api.createProject(newName.trim());
      setShowCreate(false);
      setNewName("");
      router.push(`/projects/${p.id}`);
    } catch (e) {
      setCreateError(e instanceof ApiError ? e.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="h-screen flex items-center justify-center bg-[var(--bg-primary)] text-[var(--text-secondary)] text-sm">
        Loading…
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <TopNav title="Your projects" />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-semibold text-[#e6edf3]">Projects</h2>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                Each project is an isolated MPAC session. Invite collaborators or
                AI agents to join.
              </p>
            </div>
            <Button size="sm" onClick={() => setShowCreate(true)} className={greenBtnClass + " w-auto"}>
              <Plus className="size-4" />
              New project
            </Button>
          </div>

          {showCreate && (
            <form
              onSubmit={onCreate}
              className="mb-6 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg p-4"
            >
              <label className="block text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide mb-2">
                Project name
              </label>
              {createError && (
                <Alert variant="destructive" className="mb-3">
                  <AlertDescription>{createError}</AlertDescription>
                </Alert>
              )}
              <div className="flex gap-2">
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="my-backend-service"
                  autoFocus
                />
                <Button
                  type="submit"
                  disabled={creating || !newName.trim()}
                  className={greenBtnClass + " w-auto"}
                >
                  {creating ? "Creating…" : "Create"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setShowCreate(false);
                    setNewName("");
                    setCreateError(null);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}

          {listError && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{listError}</AlertDescription>
            </Alert>
          )}

          {loading ? (
            <div className="text-sm text-[var(--text-secondary)] py-8 text-center">
              Loading projects…
            </div>
          ) : projects.length === 0 ? (
            <div className="border border-dashed border-[var(--border)] rounded-lg p-12 text-center">
              <Folder className="size-8 mx-auto mb-2 text-[var(--text-secondary)]" />
              <div className="text-sm text-[var(--text-primary)] font-medium mb-1">
                No projects yet
              </div>
              <div className="text-xs text-[var(--text-secondary)] mb-4">
                Create your first project to start collaborating
              </div>
              <Button size="sm" variant="outline" onClick={() => setShowCreate(true)}>
                <Plus className="size-4" />
                New project
              </Button>
            </div>
          ) : (
            <ul className="space-y-2">
              {projects.map((p) => {
                const isOwner = p.owner_id === user.user_id;
                // Destructive action sits OUTSIDE the <Link> rather than
                // nested inside — nesting <button> in <a> is invalid HTML
                // and both would compete for the click. Flexbox + a shared
                // bg on the outer wrapper gets us the same "whole row is
                // clickable" feel without the accessibility pitfall.
                return (
                  <li
                    key={p.id}
                    className="group bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-lg flex items-stretch transition-colors"
                  >
                    <Link
                      href={`/projects/${p.id}`}
                      className="flex-1 min-w-0 p-4"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="font-medium text-[#e6edf3] truncate">
                            {p.name}
                          </div>
                          <div className="text-xs text-[var(--text-secondary)] mt-1 font-mono truncate">
                            {p.session_id}
                          </div>
                        </div>
                        <div className="text-xs text-[var(--text-secondary)] flex-shrink-0">
                          {isOwner ? (
                            <span className="px-2 py-0.5 bg-[var(--accent)]/10 text-[var(--accent)] rounded">
                              owner
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] rounded">
                              member
                            </span>
                          )}
                        </div>
                      </div>
                    </Link>
                    <div className="flex items-center pr-3">
                      {isOwner ? (
                        <button
                          type="button"
                          onClick={() =>
                            setPendingAction({ kind: "delete", project: p })
                          }
                          title="Delete this project for everyone"
                          className="p-2 rounded-md text-[var(--text-secondary)] hover:text-[var(--red)] hover:bg-[var(--red)]/10 transition-colors opacity-60 group-hover:opacity-100"
                          aria-label={`Delete ${p.name}`}
                        >
                          <Trash2 className="size-4" />
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() =>
                            setPendingAction({ kind: "leave", project: p })
                          }
                          title="Leave this project"
                          className="p-2 rounded-md text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors opacity-60 group-hover:opacity-100"
                          aria-label={`Leave ${p.name}`}
                        >
                          <LogOut className="size-4" />
                        </button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </main>

      <DestructiveConfirmModal
        open={pendingAction !== null}
        onOpenChange={(open) => {
          if (!open) setPendingAction(null);
        }}
        title={
          pendingAction?.kind === "delete"
            ? `Delete project "${pendingAction.project.name}"?`
            : pendingAction?.kind === "leave"
              ? `Leave "${pendingAction.project.name}"?`
              : ""
        }
        body={
          pendingAction?.kind === "delete"
            ? "This permanently removes all files, invites, and tokens.\n\n" +
              "Every member (including Claude agents) loses access immediately.\n\n" +
              "This can't be undone."
            : pendingAction?.kind === "leave"
              ? "Your browser session and any Claude relay you have running will lose access.\n\n" +
                "The project stays put for the owner and other members — they can re-invite you later if needed."
              : ""
        }
        confirmLabel={pendingAction?.kind === "delete" ? "Delete" : "Leave"}
        onConfirm={runPendingAction}
        busy={actionBusy}
      />
    </div>
  );
}
