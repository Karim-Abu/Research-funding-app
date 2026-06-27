import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"
import { login } from "@/lib/session"
import {
  getReview,
  createApproval,
  createHumanDecision,
  startRecheck,
  ReviewError,
} from "@/lib/review"

function pkg(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "r1",
    requirements: [],
    fields: [],
    findings: [],
    approval_status: "open",
    blocker_count: 0,
    warning_count: 1,
    open_issues: [],
    review_package_version: "rpv-abc123",
    current_approval_scope_hash: "a".repeat(64),
    recheck_required: false,
    stale_finding_count: 0,
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

describe("review client", () => {
  beforeEach(() => setBackendMode("live"))
  afterEach(() => setBackendMode("mock"))

  it("getReview parses the package", async () => {
    server.use(http.get("/api/runs/r1/review", () => HttpResponse.json(pkg())))
    const result = await getReview("r1")
    expect(result.review_package_version).toBe("rpv-abc123")
    expect(result.approval_status).toBe("open")
  })

  it("createApproval sends expected hash/version + confirm flag + CSRF", async () => {
    await authed()
    let body: Record<string, unknown> | null = null
    let csrf: string | null = null
    server.use(
      http.post("/api/runs/r1/approvals", async ({ request }) => {
        csrf = request.headers.get("x-csrf-token")
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(
          {
            approval_id: "ap1",
            run_id: "r1",
            scope: "field",
            status: "approved",
            approval_scope_hash: "a".repeat(64),
            approved_by: "u",
            created_at: new Date().toISOString(),
          },
          { status: 201 }
        )
      })
    )
    const approval = await createApproval(
      "r1",
      pkg(),
      "field",
      "INTRO.APP.ABSTRACT"
    )
    expect(approval.status).toBe("approved")
    expect(body!.expected_approval_scope_hash).toBe("a".repeat(64))
    expect(body!.expected_review_package_version).toBe("rpv-abc123")
    expect(body!.confirm_not_submission_approval).toBe(true)
    expect(csrf).toBe("tok")
  })

  it("createApproval surfaces the blocked reason on 409", async () => {
    await authed()
    server.use(
      http.post("/api/runs/r1/approvals", () =>
        HttpResponse.json(
          { code: "approval_blocked", detail: "Approval is blocked: placeholder:X" },
          { status: 409 }
        )
      )
    )
    await expect(
      createApproval("r1", pkg(), "run", "r1")
    ).rejects.toMatchObject({ code: "approval_blocked" })
  })

  it("createHumanDecision posts the typed decision with an idempotency key", async () => {
    await authed()
    let key: string | null = null
    server.use(
      http.post("/api/runs/r1/human-decisions", async ({ request }) => {
        key = request.headers.get("idempotency-key")
        return HttpResponse.json(
          {
            target_type: "portal_field_draft",
            target_id: "d1",
            action: "request_changes",
            comment: "Bitte ergänzen.",
            decision_id: "dec1",
            user_id: "u",
            run_id: "r1",
            created_at: new Date().toISOString(),
          },
          { status: 201 }
        )
      })
    )
    const decision = await createHumanDecision("r1", {
      target_type: "portal_field_draft",
      target_id: "d1",
      action: "request_changes",
      comment: "Bitte ergänzen.",
    })
    expect(decision.decision_id).toBe("dec1")
    expect(key).toBeTruthy()
  })

  it("startRecheck posts then polls the operation to success", async () => {
    await authed()
    server.use(
      http.post("/api/runs/r1/rechecks", () =>
        HttpResponse.json(
          { operation_id: "op1", resource_type: "recheck", resource_id: "r1", status: "queued", poll_url: "/api/operations/op1" },
          { status: 202 }
        )
      ),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1",
          resource_type: "recheck",
          resource_id: "r1",
          status: "succeeded",
          created_at: new Date().toISOString(),
        })
      )
    )
    await expect(startRecheck("r1", "rpv-abc123")).resolves.toBeUndefined()
  })

  it("startRecheck rejects on a stale review package (409)", async () => {
    await authed()
    server.use(
      http.post("/api/runs/r1/rechecks", () =>
        HttpResponse.json({ code: "review_package_stale" }, { status: 409 })
      )
    )
    await expect(startRecheck("r1", "rpv-old")).rejects.toBeInstanceOf(ReviewError)
  })
})
