// Session client for the live slice. Talks only to the same-origin BFF
// (/api/session, /api/me). The CSRF token is held in memory (never persisted)
// and attached to mutating requests. In mock mode these calls never hit the
// network; a stable mock identity keeps the existing demo behaviour.

import { isLive } from "./app-mode"
import { currentUser as mockUser } from "./mock-data"

export type EffectiveRole = "lead_admin" | "member"

export interface SessionUser {
  user_id: string
  name: string
  email: string
  effective_role: EffectiveRole
  display_label?: string | null
}

interface SessionResponse {
  user: SessionUser
  csrf_token: string
}

let csrfToken: string | null = null

export function getCsrfToken(): string | null {
  return csrfToken
}

const MOCK_SESSION_USER: SessionUser = {
  user_id: "mock-user",
  name: mockUser.name,
  email: "demo@example.test",
  effective_role: mockUser.role,
  display_label: mockUser.displayRole,
}

export async function login(
  email: string,
  password: string
): Promise<SessionUser> {
  if (!isLive("session")) {
    csrfToken = "mock-csrf"
    return MOCK_SESSION_USER
  }
  const res = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    throw new Error(res.status === 401 ? "invalid_credentials" : "login_failed")
  }
  const data = (await res.json()) as SessionResponse
  csrfToken = data.csrf_token
  return data.user
}

export async function bootstrapSession(): Promise<SessionUser | null> {
  if (!isLive("session")) {
    csrfToken = "mock-csrf"
    return MOCK_SESSION_USER
  }
  const res = await fetch("/api/session", { method: "GET" })
  if (!res.ok) {
    csrfToken = null
    return null
  }
  const data = (await res.json()) as SessionResponse
  csrfToken = data.csrf_token
  return data.user
}

export async function logout(): Promise<void> {
  if (!isLive("session")) {
    csrfToken = null
    return
  }
  await fetch("/api/session", {
    method: "DELETE",
    headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
  })
  csrfToken = null
}
