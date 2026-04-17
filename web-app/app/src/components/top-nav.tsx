"use client";
// Shared top navigation for logged-in pages (projects list, workspace).

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export function TopNav({ title, children }: { title?: string; children?: React.ReactNode }) {
  const { user, logout } = useAuth();
  const router = useRouter();

  function onLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className="h-12 bg-[var(--bg-secondary)] border-b border-[var(--border)] flex items-center px-4 gap-4 flex-shrink-0">
      <Link
        href="/projects"
        className="inline-flex items-center gap-2 text-[var(--accent)] font-semibold text-sm hover:opacity-80 transition-opacity"
      >
        <span className="w-6 h-6 rounded-md bg-[var(--accent)]/10 ring-1 ring-[var(--accent)]/30 flex items-center justify-center text-xs">
          M
        </span>
        MPAC
      </Link>
      {title && (
        <>
          <div className="h-4 w-px bg-[var(--border)]" />
          <h1 className="text-sm font-semibold text-[#e6edf3]">{title}</h1>
        </>
      )}
      <div className="flex-1 flex items-center gap-2 justify-end">
        {children}
        {user && (
          <div className="flex items-center gap-2 pl-3 ml-1 border-l border-[var(--border)]">
            <div
              className="w-7 h-7 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center text-xs font-medium text-[var(--text-primary)]"
              title={user.email}
            >
              {user.display_name[0]?.toUpperCase() ?? "?"}
            </div>
            <span className="text-xs text-[var(--text-primary)] hidden sm:inline">
              {user.display_name}
            </span>
            <button
              onClick={onLogout}
              className="text-xs px-2 py-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
