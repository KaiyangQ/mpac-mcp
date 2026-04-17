"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useRedirectIfAuthed } from "@/lib/redirect-hooks";
import { ApiError } from "@/lib/api";
import {
  AuthShell,
  inputClass,
  labelClass,
  primaryBtnClass,
  errorClass,
} from "@/components/auth-shell";

function RegisterForm() {
  const { register } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/projects";
  useRedirectIfAuthed(next);

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (password.length < 6) {
      setErr("Password must be at least 6 characters");
      return;
    }
    setBusy(true);
    try {
      await register(email, password, displayName.trim() || email.split("@")[0]);
      router.replace(next);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Collaborate with humans and AI agents in shared projects"
      footer={
        <>
          Already have an account?{" "}
          <Link
            href={`/login${next !== "/projects" ? `?next=${encodeURIComponent(next)}` : ""}`}
            className="text-[var(--accent)] hover:underline"
          >
            Sign in
          </Link>
        </>
      }
    >
      {err && <div className={errorClass}>{err}</div>}
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className={labelClass}>Display name</label>
          <input
            type="text"
            value={displayName}
            autoFocus
            onChange={(e) => setDisplayName(e.target.value)}
            className={inputClass}
            placeholder="Kaiyang"
          />
        </div>
        <div>
          <label className={labelClass}>Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label className={labelClass}>Password</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
            placeholder="At least 6 characters"
          />
        </div>
        <button type="submit" disabled={busy} className={primaryBtnClass}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
    </AuthShell>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<AuthShell title="Create your account" />}>
      <RegisterForm />
    </Suspense>
  );
}
