"use client";
// Shared redirect behaviour for auth-aware pages.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth-context";

/** Redirect unauthenticated users to `/login` (with a `next=` hint). */
export function useRequireAuth(nextPath?: string) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!user) {
      const params = nextPath ? `?next=${encodeURIComponent(nextPath)}` : "";
      router.replace(`/login${params}`);
    }
  }, [user, isLoading, nextPath, router]);

  return { user, isLoading };
}

/** Redirect already-authenticated users away from the login/register pages. */
export function useRedirectIfAuthed(to: string = "/projects") {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (user) router.replace(to);
  }, [user, isLoading, to, router]);

  return { user, isLoading };
}
