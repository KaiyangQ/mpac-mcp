"use client";
// Auth context — bootstraps from stored JWT on mount, exposes current user
// and login/register/logout helpers to the whole app.

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  api,
  ApiError,
  type MeResponse,
  clearStoredJwt,
  getStoredJwt,
  setStoredJwt,
} from "./api";

type AuthState = {
  user: MeResponse | null;
  /** True while verifying the stored JWT on first mount. */
  isLoading: boolean;
  /** The stored JWT if any — consumers rarely need this. */
  hasToken: boolean;
};

type AuthActions = {
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    displayName: string,
    inviteCode: string,
  ) => Promise<void>;
  logout: () => void;
  /** Force a re-fetch of /me, e.g. after changing display_name. */
  refresh: () => Promise<void>;
};

const AuthContext = createContext<(AuthState & AuthActions) | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasToken, setHasToken] = useState(false);

  const bootstrap = useCallback(async () => {
    const jwt = getStoredJwt();
    setHasToken(!!jwt);
    if (!jwt) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch (err) {
      // JWT expired or bad — clear and treat as logged out.
      if (err instanceof ApiError && err.status === 401) {
        clearStoredJwt();
        setHasToken(false);
      }
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login({ email, password });
    setStoredJwt(res.token);
    setHasToken(true);
    setUser({ user_id: res.user_id, email: res.email, display_name: res.display_name });
  }, []);

  const register = useCallback(
    async (
      email: string,
      password: string,
      displayName: string,
      inviteCode: string,
    ) => {
      const res = await api.register({
        email,
        password,
        display_name: displayName,
        invite_code: inviteCode,
      });
      setStoredJwt(res.token);
      setHasToken(true);
      setUser({ user_id: res.user_id, email: res.email, display_name: res.display_name });
    },
    [],
  );

  const logout = useCallback(() => {
    clearStoredJwt();
    setHasToken(false);
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    await bootstrap();
  }, [bootstrap]);

  return (
    <AuthContext.Provider
      value={{ user, isLoading, hasToken, login, register, logout, refresh }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
