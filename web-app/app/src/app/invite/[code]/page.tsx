"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError, type InvitePreview } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { AuthShell, greenBtnClass } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function InviteAcceptPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = use(params);
  const nextPath = `/invite/${code}`;

  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState<string | null>(null);

  // Fetch preview (public, no auth required)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const p = await api.previewInvite(code);
        if (!cancelled) setPreview(p);
      } catch (e) {
        if (!cancelled) {
          setPreviewError(
            e instanceof ApiError ? e.message : "Invite not found",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [code]);

  async function onAccept() {
    if (!user) return;
    setAcceptError(null);
    setAccepting(true);
    try {
      const tokenRes = await api.acceptInvite(code);
      // Find the project via session_id lookup in /projects list.
      const list = await api.listProjects();
      const match = list.projects.find(
        (p) => p.session_id === tokenRes.session_id,
      );
      if (match) {
        router.replace(`/projects/${match.id}`);
      } else {
        router.replace("/projects");
      }
    } catch (e) {
      setAcceptError(
        e instanceof ApiError ? e.message : "Failed to accept invite",
      );
      setAccepting(false);
    }
  }

  if (loading) {
    return <AuthShell title="Loading invite…" />;
  }

  if (previewError || !preview) {
    return (
      <AuthShell title="Invite not found" subtitle="This link may have been revoked or mistyped.">
        <Alert variant="destructive" className="mb-3">
          <AlertDescription>{previewError ?? "Unknown error"}</AlertDescription>
        </Alert>
        <Link
          href="/"
          className="block text-center text-sm text-[var(--accent)] hover:underline"
        >
          Go home
        </Link>
      </AuthShell>
    );
  }

  if (preview.used) {
    return (
      <AuthShell
        title="Already used"
        subtitle={`This invite to ${preview.project_name} has already been accepted. Ask ${preview.invited_by} for a new one.`}
      >
        <Link
          href={user ? "/projects" : "/login"}
          className="block text-center text-sm text-[var(--accent)] hover:underline"
        >
          {user ? "Go to your projects" : "Sign in"}
        </Link>
      </AuthShell>
    );
  }

  if (authLoading) {
    return <AuthShell title="Loading…" />;
  }

  // Not logged in → pitch register/login, preserving the invite path as `next`.
  if (!user) {
    return (
      <AuthShell
        title={`${preview.invited_by} invited you`}
        subtitle={
          <>
            Join <span className="text-[var(--accent)] font-medium">{preview.project_name}</span>{" "}
            and start collaborating in real time.
          </>
        }
      >
        <div className="space-y-3">
          <Button asChild className={greenBtnClass}>
            <Link href={`/register?next=${encodeURIComponent(nextPath)}`}>
              Create account to join
            </Link>
          </Button>
          <Button asChild variant="outline" className="w-full">
            <Link href={`/login?next=${encodeURIComponent(nextPath)}`}>
              Sign in to join
            </Link>
          </Button>
        </div>
      </AuthShell>
    );
  }

  // Logged in → show Accept button.
  return (
    <AuthShell
      title={`Join ${preview.project_name}`}
      subtitle={`Invited by ${preview.invited_by}. You'll get a token scoped to this project only.`}
    >
      {acceptError && (
        <Alert variant="destructive" className="mb-3">
          <AlertDescription>{acceptError}</AlertDescription>
        </Alert>
      )}
      <div className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-md p-3 mb-4 text-xs">
        <div className="flex justify-between text-[var(--text-secondary)]">
          <span>Project</span>
          <span className="text-[var(--text-primary)] font-medium">{preview.project_name}</span>
        </div>
        <div className="flex justify-between mt-1.5 text-[var(--text-secondary)]">
          <span>Session</span>
          <span className="text-[var(--text-primary)] font-mono">{preview.session_id}</span>
        </div>
        <div className="flex justify-between mt-1.5 text-[var(--text-secondary)]">
          <span>You&apos;ll join as</span>
          <span className="text-[var(--text-primary)]">{user.display_name}</span>
        </div>
      </div>
      <Button onClick={onAccept} disabled={accepting} className={greenBtnClass}>
        {accepting ? "Joining…" : "Accept invite"}
      </Button>
    </AuthShell>
  );
}
