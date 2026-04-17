"use client";
// Client-side provider wrapper. Keeps the root layout a Server Component
// so we still get metadata + font optimization.

import { AuthProvider } from "@/lib/auth-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
