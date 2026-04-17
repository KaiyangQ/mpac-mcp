"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useRedirectIfAuthed } from "@/lib/redirect-hooks";
import { ApiError } from "@/lib/api";
import { AuthShell, labelClass, greenBtnClass } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";

function RegisterForm() {
  const { register } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/projects";
  // Allow prefilling invite code via ?invite=... — makes sharing links easy.
  const presetInvite = searchParams.get("invite") || "";
  useRedirectIfAuthed(next);

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState(presetInvite);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!inviteCode.trim()) {
      setErr("An invite code is required for the beta");
      return;
    }
    if (password.length < 6) {
      setErr("Password must be at least 6 characters");
      return;
    }
    setBusy(true);
    try {
      await register(
        email,
        password,
        displayName.trim() || email.split("@")[0],
        inviteCode.trim(),
      );
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
      subtitle="Semi-public beta — you need an invite code from Kaiyang to sign up."
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
      {err && (
        <Alert variant="destructive" className="mb-3">
          <AlertDescription>{err}</AlertDescription>
        </Alert>
      )}
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className={labelClass}>Invite code</label>
          <Input
            type="text"
            required
            value={inviteCode}
            autoFocus={!presetInvite}
            onChange={(e) => setInviteCode(e.target.value)}
            placeholder="mpac-beta-xxxx"
          />
        </div>
        <div>
          <label className={labelClass}>Display name</label>
          <Input
            type="text"
            value={displayName}
            autoFocus={!!presetInvite}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Kaiyang"
          />
        </div>
        <div>
          <label className={labelClass}>Email</label>
          <Input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label className={labelClass}>Password</label>
          <Input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 6 characters"
          />
        </div>
        <Button type="submit" disabled={busy} className={greenBtnClass}>
          {busy ? "Creating…" : "Create account"}
        </Button>
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
