"use client";
// Root gateway: authed users go to /projects, everyone else to /login.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function RootGateway() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    router.replace(user ? "/projects" : "/login");
  }, [user, isLoading, router]);

  return (
    <div className="h-screen flex items-center justify-center bg-[var(--bg-primary)] text-[var(--text-secondary)]">
      <span className="text-sm">Loading…</span>
    </div>
  );
}
