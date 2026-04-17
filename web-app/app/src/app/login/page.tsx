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

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/projects";
  useRedirectIfAuthed(next);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(email, password);
      router.replace(next);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your MPAC workspace"
      footer={
        <>
          No account?{" "}
          <Link
            href={`/register${next !== "/projects" ? `?next=${encodeURIComponent(next)}` : ""}`}
            className="text-[var(--accent)] hover:underline"
          >
            Create one
          </Link>
        </>
      }
    >
      {err && <div className={errorClass}>{err}</div>}
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className={labelClass}>Email</label>
          <input
            type="email"
            required
            autoFocus
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
            placeholder="••••••••"
          />
        </div>
        <button type="submit" disabled={busy} className={primaryBtnClass}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </AuthShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<AuthShell title="Welcome back" />}>
      <LoginForm />
    </Suspense>
  );
}
