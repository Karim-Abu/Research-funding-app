import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"
import { login } from "@/lib/session"
import { RunError } from "@/lib/runs"
import {
  createProcessingConfirmation,
  POLICY_VERSION,
} from "@/lib/processing-confirmations"

describe("processing-confirmation client (live)", () => {
  beforeEach(() => setBackendMode("live"))
  afterEach(() => setBackendMode("mock"))

  it("posts the confirmation with policy version, CSRF + Idempotency-Key", async () => {
    server.use(
      http.post("/api/session", () =>
        HttpResponse.json({
          user: { user_id: "u", name: "T", email: "t@x.test", effective_role: "member" },
          csrf_token: "tok",
        })
      )
    )
    await login("t@x.test", "pw")
    let headers: Headers | null = null
    let body: Record<string, unknown> | null = null
    server.use(
      http.post("/api/projects/p1/processing-confirmations", async ({ request }) => {
        headers = request.headers
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(
          {
            confirmation_id: "c1",
            project_id: "p1",
            created_by: "u",
            status: "valid",
            source_version_ids: ["sv1"],
            policy_version: POLICY_VERSION,
            created_at: new Date().toISOString(),
          },
          { status: 201 }
        )
      })
    )
    const res = await createProcessingConfirmation("p1", ["sv1"])
    expect(res.confirmation_id).toBe("c1")
    expect(res.status).toBe("valid")
    expect(body!.processing_mode).toBe("cloud_assisted")
    expect(body!.accepted_policy_version).toBe(POLICY_VERSION)
    expect(body!.expires_after_one_run).toBe(true)
    expect(body!.source_version_ids).toEqual(["sv1"])
    expect(headers!.get("x-csrf-token")).toBe("tok")
    expect((headers!.get("idempotency-key") ?? "").length).toBeGreaterThanOrEqual(8)
  })

  it("maps a 403 ineligible response to a user-safe permission error", async () => {
    server.use(
      http.post("/api/projects/p1/processing-confirmations", () =>
        HttpResponse.json({ code: "cloud_not_eligible_for_classification" }, { status: 403 })
      )
    )
    let caught: RunError | null = null
    try {
      await createProcessingConfirmation("p1", ["sv1"])
    } catch (e) {
      caught = e as RunError
    }
    expect(caught?.status).toBe(403)
    expect(caught?.message).toContain("keine Berechtigung")
  })
})
