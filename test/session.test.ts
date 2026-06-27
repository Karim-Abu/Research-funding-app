import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"
import { bootstrapSession, getCsrfToken, login, logout } from "@/lib/session"

const USER = {
  user_id: "u1",
  name: "Anna Keller",
  email: "anna.keller@example.test",
  effective_role: "lead_admin" as const,
}

describe("session client (live mode)", () => {
  beforeEach(() => setBackendMode("live"))
  afterEach(() => setBackendMode("mock"))

  it("login returns the user and stores the CSRF token", async () => {
    server.use(
      http.post("/api/session", () =>
        HttpResponse.json({ user: USER, csrf_token: "csrf-123" })
      )
    )
    const user = await login("anna.keller@example.test", "pw")
    expect(user.email).toBe("anna.keller@example.test")
    expect(getCsrfToken()).toBe("csrf-123")
  })

  it("login throws invalid_credentials on 401", async () => {
    server.use(
      http.post("/api/session", () =>
        HttpResponse.json({ code: "invalid_credentials" }, { status: 401 })
      )
    )
    await expect(login("anna.keller@example.test", "bad")).rejects.toThrow(
      "invalid_credentials"
    )
  })

  it("bootstrap returns null when unauthenticated", async () => {
    server.use(
      http.get("/api/session", () => new HttpResponse(null, { status: 401 }))
    )
    expect(await bootstrapSession()).toBeNull()
  })

  it("logout sends the X-CSRF-Token and clears it", async () => {
    server.use(
      http.post("/api/session", () =>
        HttpResponse.json({ user: USER, csrf_token: "tok" })
      )
    )
    await login("anna.keller@example.test", "pw")

    let sentCsrf: string | null = null
    server.use(
      http.delete("/api/session", ({ request }) => {
        sentCsrf = request.headers.get("x-csrf-token")
        return new HttpResponse(null, { status: 204 })
      })
    )
    await logout()
    expect(sentCsrf).toBe("tok")
    expect(getCsrfToken()).toBeNull()
  })
})
