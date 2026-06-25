import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"
import { login } from "@/lib/session"
import { createExport, getExport, ExportError } from "@/lib/exports"

function artifact(overrides: Record<string, unknown> = {}) {
  return {
    export_id: "ex1",
    run_id: "r1",
    type: "markdown",
    status: "available",
    draft_marked: true,
    filename: "Projekt_Zusammenfassung_ENTWURF.md",
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

async function authed() {
  server.use(
    http.post("/api/session", () =>
      HttpResponse.json({
        user: { user_id: "u", name: "A", email: "a@x.test", effective_role: "lead_admin" },
        csrf_token: "tok",
      })
    )
  )
  await login("a@x.test", "pw")
}

describe("exports client", () => {
  beforeEach(() => setBackendMode("live"))
  afterEach(() => setBackendMode("mock"))

  it("getExport maps the artifact", async () => {
    server.use(http.get("/api/exports/ex1", () => HttpResponse.json(artifact())))
    const result = await getExport("ex1")
    expect(result.status).toBe("available")
    expect(result.draft_marked).toBe(true)
  })

  it("createExport posts, polls the operation, and returns the artifact", async () => {
    await authed()
    let body: Record<string, unknown> | null = null
    let csrf: string | null = null
    let key: string | null = null
    server.use(
      http.post("/api/runs/r1/exports", async ({ request }) => {
        csrf = request.headers.get("x-csrf-token")
        key = request.headers.get("idempotency-key")
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(
          { operation_id: "op1", resource_type: "export", resource_id: "ex1", status: "queued", poll_url: "/api/operations/op1" },
          { status: 202 }
        )
      }),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1",
          resource_type: "export",
          resource_id: "ex1",
          status: "succeeded",
          created_at: new Date().toISOString(),
        })
      ),
      http.get("/api/exports/ex1", () => HttpResponse.json(artifact()))
    )
    const result = await createExport("r1", "markdown")
    expect(result.export_id).toBe("ex1")
    expect(body!.type).toBe("markdown")
    expect(body!.force_draft).toBe(false)
    expect(csrf).toBe("tok")
    expect(key).toBeTruthy()
  })

  it("createExport surfaces the 429 limit", async () => {
    await authed()
    server.use(
      http.post("/api/runs/r1/exports", () =>
        HttpResponse.json({ code: "export_limit_reached" }, { status: 429 })
      )
    )
    await expect(createExport("r1", "docx")).rejects.toMatchObject({
      code: "export_limit_reached",
    })
  })

  it("createExport rejects when the operation fails", async () => {
    await authed()
    server.use(
      http.post("/api/runs/r1/exports", () =>
        HttpResponse.json(
          { operation_id: "op2", resource_type: "export", resource_id: "ex2", status: "queued", poll_url: "/api/operations/op2" },
          { status: 202 }
        )
      ),
      http.get("/api/operations/op2", () =>
        HttpResponse.json({
          operation_id: "op2",
          resource_type: "export",
          resource_id: "ex2",
          status: "failed",
          created_at: new Date().toISOString(),
        })
      )
    )
    await expect(createExport("r1", "docx")).rejects.toBeInstanceOf(ExportError)
  })
})
