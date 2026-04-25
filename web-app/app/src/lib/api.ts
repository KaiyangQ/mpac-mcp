// Typed API client for the MPAC Web App backend.
//
// Reads JWT from localStorage on each request. SSR-safe: localStorage access
// is guarded by `typeof window !== 'undefined'`. Server Components shouldn't
// call this client — it's for Client Components and effects only.

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001";

const JWT_STORAGE_KEY = "mpac_jwt";

// ── Types mirroring api/schemas.py ────────────────────────

export type AuthResponse = {
  token: string;
  user_id: number;
  email: string;
  display_name: string;
};

export type MeResponse = {
  user_id: number;
  email: string;
  display_name: string;
};

export type Project = {
  id: number;
  session_id: string;
  name: string;
  owner_id: number;
  created_at: string;
};

export type ProjectListResponse = {
  projects: Project[];
};

export type TokenResponse = {
  // Membership descriptor, NOT a capability — pre-2026-04-25 this also
  // carried the raw MPAC bearer ``token_value``, but the browser never
  // used it (WS auth uses the JWT) and shipping it expanded XSS blast
  // radius. Backend dropped the field; frontend mirrors that.
  session_id: string;
  roles: string[];
};

export type InviteResponse = {
  invite_code: string;
  project_name: string;
  session_id: string;
};

export type InvitePreview = {
  invite_code: string;
  project_name: string;
  session_id: string;
  invited_by: string;
  used: boolean;
};

export type AnthropicKeyStatus = {
  has_key: boolean;
  key_preview?: string | null;
};

export type AgentTokenResponse = {
  token_value: string;
  project_id: number;
  relay_url: string;
  /** Bash one-liner — macOS / Linux / WSL / Git Bash. */
  launch_command: string;
  /** PowerShell one-liner for Windows users (optional: missing in
   * responses from older web-app versions). */
  launch_command_windows?: string | null;
};

export type AgentStatus = {
  connected: boolean;
  display_name?: string | null;
};

export type ProjectFileListItem = {
  path: string;
  updated_at: string;
};

export type ProjectFileListResponse = {
  files: ProjectFileListItem[];
};

export type ProjectFileContent = {
  path: string;
  content: string;
  updated_at: string;
};

// ── Storage helpers ───────────────────────────────────────

export function getStoredJwt(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(JWT_STORAGE_KEY);
}

export function setStoredJwt(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(JWT_STORAGE_KEY, token);
}

export function clearStoredJwt(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(JWT_STORAGE_KEY);
}

// ── Core fetch wrapper ────────────────────────────────────

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: { auth?: boolean } = { auth: true },
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (opts.auth !== false) {
    const jwt = getStoredJwt();
    if (jwt) headers["Authorization"] = `Bearer ${jwt}`;
  }
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    // Send + accept cookies on every request. Required for the WS-auth
    // cookie set on /login + /register to actually land in the browser
    // jar in dev (frontend :3000 ↔ backend :8001 are cross-origin and the
    // default ``credentials: "same-origin"`` would drop Set-Cookie). Prod
    // is same-origin so this is a no-op there.
    credentials: "include",
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      if (errBody.detail) detail = errBody.detail;
    } catch {
      /* noop */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ── Auth ──────────────────────────────────────────────────

export const api = {
  register: (payload: {
    email: string;
    password: string;
    display_name: string;
    invite_code: string;
  }) =>
    request<AuthResponse>("POST", "/api/register", payload, { auth: false }),

  login: (payload: { email: string; password: string }) =>
    request<AuthResponse>("POST", "/api/login", payload, { auth: false }),

  me: () => request<MeResponse>("GET", "/api/me"),

  // ── Projects ────────────────────────────────────────────

  listProjects: () => request<ProjectListResponse>("GET", "/api/projects"),

  createProject: (name: string) =>
    request<Project>("POST", "/api/projects", { name }),

  getProject: (projectId: number) =>
    request<Project>("GET", `/api/projects/${projectId}`),

  /** Owner-only. Destroys the project + all files, tokens, invites. */
  deleteProject: (projectId: number) =>
    request<void>("DELETE", `/api/projects/${projectId}`),

  /** Owner-only. Overwrites the canonical notes_app demo files back
   * to seed state. URL/members/invites unchanged. */
  resetProjectToSeed: (projectId: number) =>
    request<void>("POST", `/api/projects/${projectId}/reset-to-seed`),

  /** Non-owner-only. Revokes the caller's tokens for this project. */
  leaveProject: (projectId: number) =>
    request<void>("POST", `/api/projects/${projectId}/leave`),

  // ── Tokens ──────────────────────────────────────────────

  getMpacToken: (projectId: number) =>
    request<TokenResponse>("GET", `/api/projects/${projectId}/token`),

  // ── Invites ─────────────────────────────────────────────

  createInvite: (projectId: number, roles: string[] = ["contributor"]) =>
    request<InviteResponse>("POST", `/api/projects/${projectId}/invite`, { roles }),

  previewInvite: (code: string) =>
    request<InvitePreview>("GET", `/api/invites/${code}`, undefined, { auth: false }),

  acceptInvite: (code: string) =>
    request<TokenResponse>("POST", "/api/invites/accept", { invite_code: code }),

  // ── Settings: BYOK Anthropic key ────────────────────────

  getAnthropicKey: () =>
    request<AnthropicKeyStatus>("GET", "/api/settings/anthropic-key"),

  setAnthropicKey: (apiKey: string) =>
    request<AnthropicKeyStatus>("PUT", "/api/settings/anthropic-key", {
      api_key: apiKey,
    }),

  deleteAnthropicKey: () =>
    request<AnthropicKeyStatus>("DELETE", "/api/settings/anthropic-key"),

  // ── Project files (Phase F) ─────────────────────────────

  listProjectFiles: (projectId: number) =>
    request<ProjectFileListResponse>("GET", `/api/projects/${projectId}/files`),

  readProjectFile: (projectId: number, path: string) =>
    request<ProjectFileContent>(
      "GET",
      `/api/projects/${projectId}/files/content?path=${encodeURIComponent(path)}`,
    ),

  writeProjectFile: (projectId: number, path: string, content: string) =>
    request<ProjectFileContent>(
      "PUT",
      `/api/projects/${projectId}/files/content`,
      { path, content },
    ),

  deleteProjectFile: (projectId: number, path: string) =>
    request<{ status: string; path: string }>(
      "DELETE",
      `/api/projects/${projectId}/files?path=${encodeURIComponent(path)}`,
    ),

  // ── Chat (Phase E) ──────────────────────────────────────

  chat: (projectId: number, message: string) =>
    request<{ reply: string }>("POST", "/api/chat", {
      project_id: projectId,
      message,
    }),

  // ── Agent relay (Path B: local Claude Code bridge) ──────

  mintAgentToken: (projectId: number) =>
    request<AgentTokenResponse>("POST", `/api/projects/${projectId}/agent-token`),

  getAgentStatus: (projectId: number) =>
    request<AgentStatus>("GET", `/api/projects/${projectId}/agent-status`),
};

export { API_URL };
