"use client";
// Centered dark auth panel used by /login, /register, /invite/[code].

import Link from "next/link";

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: React.ReactNode;
  children?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="h-screen flex flex-col items-center justify-center bg-[var(--bg-primary)] px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-[var(--accent)] font-semibold text-xl"
          >
            <span className="w-8 h-8 rounded-lg bg-[var(--accent)]/10 ring-1 ring-[var(--accent)]/30 flex items-center justify-center">
              M
            </span>
            MPAC
          </Link>
        </div>
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-xl p-6 shadow-xl">
          <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">{title}</h1>
          {subtitle && (
            <p className="text-sm text-[var(--text-secondary)] mb-5">{subtitle}</p>
          )}
          {children}
        </div>
        {footer && <div className="mt-4 text-center text-sm text-[var(--text-secondary)]">{footer}</div>}
      </div>
    </div>
  );
}

export const labelClass =
  "block text-xs font-medium text-[var(--text-secondary)] mb-1.5 uppercase tracking-wide";

// Style classes for a "success green" shadcn <Button> (primary CTA).
// Kept here so login/register/invite/projects share the same green.
export const greenBtnClass =
  "w-full bg-[#238636] hover:bg-[#2ea043] text-white disabled:bg-[#238636]/50";
