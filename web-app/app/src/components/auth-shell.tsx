"use client";
// Split-screen auth layout used by /login, /register, /invite/[code].
//
// Desktop (lg+):   [ branding pitch ][ form card ]  — 50/50 grid.
// Mobile  (< lg):  form only, with a compact logo header and the pitch
//                  hidden (screen real estate is too precious).
//
// Consumers pass the form as children; title / subtitle / footer are
// optional slots. Use `pitch={false}` for tiny shells like "Loading invite…".

import Link from "next/link";
import { Code2, Sparkles, Users, Zap } from "lucide-react";

type Props = {
  title: string;
  subtitle?: React.ReactNode;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  /** Hide the left branding panel (e.g. for loading / error placeholders). */
  pitch?: boolean;
};

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
  pitch = true,
}: Props) {
  // Root <body> has `overflow: hidden; height: 100vh` (needed for the IDE
  // workspace page). Auth pages fight that by taking over the full viewport
  // with a fixed container that scrolls its own contents — so tall forms
  // still work on short screens.
  return (
    <div className="fixed inset-0 bg-[var(--bg-primary)] text-[var(--text-primary)] overflow-auto">
      {/* Ambient background — faint radial glows. pointer-events-none so it
          never steals clicks from the form below. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-0"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 80% 60% at 15% 20%, rgba(88,166,255,0.12), transparent 60%), " +
            "radial-gradient(ellipse 60% 50% at 85% 80%, rgba(163,113,247,0.10), transparent 60%)",
        }}
      />

      {/* Cap the split layout at 1280px on wide screens and center it — without
          this the two panels each sprawl to ~50% of a 2K monitor and the
          content feels lost in empty padding. */}
      <div className="relative z-10 grid min-h-full lg:grid-cols-2 lg:max-w-7xl lg:mx-auto lg:w-full">
        {pitch && <PitchPanel />}
        <FormPanel title={title} subtitle={subtitle} footer={footer}>
          {children}
        </FormPanel>
      </div>
    </div>
  );
}

// ── Left: branding + product pitch (desktop only) ────────────────────

function PitchPanel() {
  return (
    <aside
      className="hidden lg:flex flex-col justify-between relative overflow-hidden px-10 py-10 xl:px-12 xl:py-12 border-r border-[var(--border)]"
      style={{
        // A richer gradient than the page's ambient — tied to primary + a
        // warm purple so the two halves feel distinct but related.
        backgroundImage:
          "linear-gradient(135deg, rgba(88,166,255,0.08) 0%, rgba(163,113,247,0.06) 45%, rgba(13,17,23,0) 100%)",
      }}
    >
      {/* Subtle grid texture — feels like "engineering" without being noisy. */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(var(--text-primary) 1px, transparent 1px), " +
            "linear-gradient(90deg, var(--text-primary) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
        }}
      />

      <div className="relative">
        <Link
          href="/"
          className="inline-flex items-center gap-3 group"
        >
          <span
            className="w-10 h-10 rounded-xl flex items-center justify-center text-base font-semibold text-white shadow-lg shadow-[#58a6ff]/20 ring-1 ring-white/10"
            style={{
              backgroundImage:
                "linear-gradient(135deg, #58a6ff 0%, #a371f7 100%)",
            }}
          >
            M
          </span>
          <span className="text-lg font-semibold tracking-tight">
            MPAC
          </span>
        </Link>
      </div>

      <div className="relative max-w-md">
        <div className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--bg-secondary)]/60 backdrop-blur px-3 py-1 text-xs text-[var(--text-secondary)] mb-4">
          <Sparkles className="size-3 text-[#a371f7]" />
          Semi-public beta · invite-only
        </div>
        <h2 className="text-3xl font-bold leading-tight tracking-tight mb-3">
          Coordinate humans and{" "}
          <span
            className="bg-clip-text text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(120deg, #58a6ff 0%, #a371f7 100%)",
            }}
          >
            AI agents
          </span>{" "}
          in the same editor.
        </h2>
        <p className="text-[var(--text-secondary)] leading-relaxed text-sm">
          MPAC is a protocol for multi-principal collaboration — so
          Claude can edit alongside your team without overwriting your
          work or hiding what it&apos;s doing.
        </p>

        <ul className="mt-6 space-y-3.5">
          <PitchBullet
            icon={<Users className="size-4" />}
            title="Real-time presence"
          >
            See which teammate (or which agent) is editing what, with
            live intent announcements on every file.
          </PitchBullet>
          <PitchBullet
            icon={<Zap className="size-4" />}
            title="Intent-first workflow"
          >
            Claim a file before you edit; conflicts surface as
            negotiations, never as silent overwrites.
          </PitchBullet>
          <PitchBullet
            icon={<Sparkles className="size-4" />}
            title="AI as a first-class peer"
          >
            Claude joins the session as a named participant — you see
            its plan, its intent, and when it leaves.
          </PitchBullet>
        </ul>
      </div>

      <div className="relative flex items-center gap-4 text-xs text-[var(--text-secondary)]">
        <a
          href="https://github.com/KaiyangQ/mpac-protocol"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 hover:text-[var(--text-primary)] transition-colors"
        >
          <Code2 className="size-3.5" />
          mpac-protocol on GitHub
        </a>
        <span className="text-[var(--border)]">·</span>
        <a
          href="https://pypi.org/project/mpac/"
          target="_blank"
          rel="noreferrer"
          className="hover:text-[var(--text-primary)] transition-colors"
        >
          pip install mpac
        </a>
      </div>
    </aside>
  );
}

function PitchBullet({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <li className="flex gap-3">
      <span
        className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ring-1 ring-white/10"
        style={{
          backgroundImage:
            "linear-gradient(135deg, rgba(88,166,255,0.15), rgba(163,113,247,0.12))",
          color: "#58a6ff",
        }}
      >
        {icon}
      </span>
      <div className="min-w-0">
        <div className="text-sm font-semibold text-[var(--text-primary)] mb-0.5">
          {title}
        </div>
        <div className="text-xs text-[var(--text-secondary)] leading-relaxed">
          {children}
        </div>
      </div>
    </li>
  );
}

// ── Right: form panel ────────────────────────────────────────────────

function FormPanel({
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
    <main className="relative flex flex-col items-center justify-center px-6 py-12 sm:px-12">
      {/* Mobile-only compact brand mark so small screens still feel branded. */}
      <Link
        href="/"
        className="lg:hidden inline-flex items-center gap-2 mb-8 text-[var(--text-primary)]"
      >
        <span
          className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-semibold text-white shadow-lg shadow-[#58a6ff]/20 ring-1 ring-white/10"
          style={{
            backgroundImage:
              "linear-gradient(135deg, #58a6ff 0%, #a371f7 100%)",
          }}
        >
          M
        </span>
        <span className="font-semibold tracking-tight">MPAC</span>
      </Link>

      <div className="w-full max-w-sm">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--text-primary)] mb-2">
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-8">
            {subtitle}
          </p>
        )}
        {!subtitle && <div className="mb-8" />}

        {children}

        {footer && (
          <div className="mt-8 text-center text-sm text-[var(--text-secondary)]">
            {footer}
          </div>
        )}
      </div>
    </main>
  );
}

// ── Shared classNames exported for form authors ──────────────────────

// Label: sentence-case, subtle, NOT uppercase admin-panel style.
export const labelClass =
  "block text-sm font-medium text-[var(--text-primary)] mb-2";

// Primary CTA: blue → purple gradient matching the brand mark + pitch accents.
// Used by <Button className={primaryBtnClass}>. Replaces the old GitHub-green.
// Small top-margin (`mt-2`) and lighter shadow (`shadow-md` instead of
// `shadow-lg`) keep the glow from visually crowding the last input field.
export const primaryBtnClass =
  "w-full h-10 mt-2 text-white font-medium shadow-md shadow-[#58a6ff]/20 " +
  "bg-gradient-to-r from-[#58a6ff] to-[#a371f7] " +
  "hover:from-[#4b97f5] hover:to-[#9460e8] " +
  "disabled:opacity-60 disabled:cursor-not-allowed";

// Back-compat alias. Several pages still import `greenBtnClass`; keep the
// export so nothing breaks — but the class now points at the new gradient.
export const greenBtnClass = primaryBtnClass;
