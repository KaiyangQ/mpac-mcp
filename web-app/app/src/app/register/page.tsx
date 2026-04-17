"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useRedirectIfAuthed } from "@/lib/redirect-hooks";
import { ApiError } from "@/lib/api";
import {
  AuthShell,
  labelClass,
  primaryBtnClass,
} from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";

function RegisterForm() {
  const { register } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/projects";
  // Allow prefilling invite code via ?invite=... — makes shareable links nice.
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
      setErr("An invite code is required for the beta.");
      return;
    }
    if (password.length < 6) {
      setErr("Password must be at least 6 characters.");
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
      title="Claim your spot"
      subtitle={
        presetInvite
          ? "Your invite code is already filled in. Finish the rest and you're in."
          : "MPAC is in semi-public beta — you'll need an invite code to continue."
      }
      footer={
        <>
          Already have an account?{" "}
          <Link
            href={`/login${next !== "/projects" ? `?next=${encodeURIComponent(next)}` : ""}`}
            className="text-[var(--accent)] hover:underline font-medium"
          >
            Sign in
          </Link>
        </>
      }
    >
      {err && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{err}</AlertDescription>
        </Alert>
      )}
      <form onSubmit={onSubmit} className="space-y-5">
        <div>
          <label className={labelClass}>Invite code</label>
          <Input
            type="text"
            required
            value={inviteCode}
            autoFocus={!presetInvite}
            onChange={(e) => setInviteCode(e.target.value)}
            placeholder="mpac-beta-xxxx"
            className="h-10 font-mono"
          />
        </div>
        <div>
          <label className={labelClass}>Display name</label>
          <Input
            type="text"
            value={displayName}
            autoFocus={!!presetInvite}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Ada Lovelace"
            className="h-10"
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
            className="h-10"
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
            className="h-10"
          />
        </div>
        <Button type="submit" disabled={busy} className={primaryBtnClass}>
          {busy ? "Creating account…" : "Create account"}
        </Button>
      </form>
    </AuthShell>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<AuthShell title="Claim your spot" />}>
      <RegisterForm />
    </Suspense>
  );
}
