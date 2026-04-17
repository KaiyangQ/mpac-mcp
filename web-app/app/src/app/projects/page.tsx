"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Folder } from "lucide-react";
import { api, ApiError, type Project } from "@/lib/api";
import { useRequireAuth } from "@/lib/redirect-hooks";
import { TopNav } from "@/components/top-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { greenBtnClass } from "@/components/auth-shell";

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
              {projects.map((p) => (
                <li key={p.id}>
                  <Link
                    href={`/projects/${p.id}`}
                    className="block bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-lg p-4 transition-colors"
                  >
                    <div className="flex items-start justify-between">
                      <div className="min-w-0">
                        <div className="font-medium text-[#e6edf3] truncate">
                          {p.name}
                        </div>
                        <div className="text-xs text-[var(--text-secondary)] mt-1 font-mono truncate">
                          {p.session_id}
                        </div>
                      </div>
                      <div className="text-xs text-[var(--text-secondary)] ml-4 flex-shrink-0">
                        {p.owner_id === user.user_id ? (
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
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
