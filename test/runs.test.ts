import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"
import { login } from "@/lib/session"
import { createRun, cancelRun, getRun, listProjectRuns, RunError } from "@/lib/runs"
import { MOCK_CAPABILITIES } from "@/lib/capabilities"

const SETTINGS = {
  processing_mode: "deterministic_only" as const,
  max_cost_chf: 0,
  max_llm_calls: 0,
  max_web_calls: 0,
}

function runDoc(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "r1",
    project_id: "p1",
    status: "created",
    current_stage: "initialize",
    progress_percent: 0,
    processing_mode: "deterministic_only",
    created_at: new Date().toISOString(),
    recheck_required: false,
    semantic_findings_stale: false,
    ...overrides,
  }
}

const ACCEPTED = {
  operation_id: "op1",
  resource_type: "run",
  resource_id: "r1",
  status: "queued",
  poll_url: "/api/v1/operations/op1",
}

describe("run client (live)", () => {
  beforeEach(() => setBackendMode("live"))
  afterEach(() => setBackendMode("mock"))

  it("createRun sends CSRF + Idempotency-Key and parses 202 AsyncAccepted", async () => {
    server.use(
      http.post("/api/session", () =>
        HttpResponse.json({
          user: { user_id: "u", name: "A", email: "a@x.test", effective_role: "lead_admin" },
          csrf_token: "tok",
        })
      )
    )
    await login("a@x.test", "pw")
    let headers: Headers | null = null
    server.use(
      http.post("/api/projects/p1/runs", ({ request }) => {
        headers = request.headers
        return HttpResponse.json(ACCEPTED, { status: 202 })
      })
    )
    const res = await createRun("p1", SETTINGS)
    expect(res.operation_id).toBe("op1")
    expect(res.poll_url).toBe("/api/v1/operations/op1")
    expect(headers!.get("x-csrf-token")).toBe("tok")
    expect((headers!.get("idempotency-key") ?? "").length).toBeGreaterThanOrEqual(8)
  })

  it("getRun returns canonical status + stage", async () => {
    server.use(
      http.get("/api/runs/r1", () =>
        HttpResponse.json(
          runDoc({ status: "completed", current_stage: "finalize_run", progress_percent: 100 })
        )
      )
    )
    const run = await getRun("r1")
    expect(run.status).toBe("completed")
    expect(run.current_stage).toBe("finalize_run")
  })

  it("listProjectRuns parses items", async () => {
    server.use(
      http.get("/api/projects/p1/runs", () =>
        HttpResponse.json({ items: [runDoc()], next_cursor: null })
      )
    )
    expect(await listProjectRuns("p1")).toHaveLength(1)
  })

  it("cancelRun returns the cancelled run", async () => {
    server.use(
      http.post("/api/runs/r1/cancel", () =>
        HttpResponse.json(runDoc({ status: "cancelled" }))
      )
    )
    expect((await cancelRun("r1")).status).toBe("cancelled")
  })

  it("maps 409 / 429 / 503 to user-safe errors", async () => {
    for (const [status, needle] of [
      [409, "läuft bereits"],
      [429, "Limit"],
      [503, "nicht verfügbar"],
    ] as const) {
      server.use(
        http.post("/api/projects/p1/runs", () =>
          HttpResponse.json({ code: "x" }, { status })
        )
      )
      let caught: RunError | null = null
      try {
        await createRun("p1", SETTINGS)
      } catch (e) {
        caught = e as RunError
      }
      expect(caught?.status).toBe(status)
      expect(caught?.message).toContain(needle)
    }
  })

  it("enables live analysis in M4 (features.runs=true) while review/export stay off", () => {
    expect(MOCK_CAPABILITIES.features.runs).toBe(true)
    expect(MOCK_CAPABILITIES.features.review).toBe(false)
    expect(MOCK_CAPABILITIES.features.export).toBe(false)
  })
})
