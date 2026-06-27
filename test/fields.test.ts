import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"
import { login } from "@/lib/session"
import {
  listFields,
  updateField,
  createEvidenceLink,
  charCount,
  FieldError,
} from "@/lib/fields"
import { MOCK_CAPABILITIES } from "@/lib/capabilities"

function draftDoc(overrides: Record<string, unknown> = {}) {
  return {
    draft_id: "d1",
    field_id: "INTRO.APP.ABSTRACT",
    field_name: "Abstract",
    status: "needs_review",
    current_version: {
      draft_version_id: "v1",
      text: "[[Angabe ergänzen: Abstract]]",
      character_count: 29,
      created_by: "template",
      created_at: new Date().toISOString(),
      content_hash: "h",
    },
    character_count: 29,
    character_limit: 300,
    open_issue_count: 1,
    evidence_links: [],
    open_issues: [],
    ...overrides,
  }
}

describe("fields client", () => {
  beforeEach(() => setBackendMode("live"))
  afterEach(() => setBackendMode("mock"))

  it("charCount counts Unicode code points (matches backend)", () => {
    expect(charCount("äöüÄÖÜß")).toBe(7)
    expect(charCount("Müller & Söhne")).toBe(14)
  })

  it("listFields parses drafts", async () => {
    server.use(
      http.get("/api/runs/r1/fields", () => HttpResponse.json([draftDoc()]))
    )
    const drafts = await listFields("r1")
    expect(drafts).toHaveLength(1)
    expect(drafts[0].current_version.created_by).toBe("template")
  })

  it("updateField sends base_version_id + CSRF", async () => {
    server.use(
      http.post("/api/session", () =>
        HttpResponse.json({
          user: { user_id: "u", name: "A", email: "a@x.test", effective_role: "lead_admin" },
          csrf_token: "tok",
        })
      )
    )
    await login("a@x.test", "pw")
    let body: Record<string, unknown> | null = null
    let csrf: string | null = null
    server.use(
      http.patch("/api/runs/r1/fields/INTRO.APP.ABSTRACT", async ({ request }) => {
        csrf = request.headers.get("x-csrf-token")
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(draftDoc({ current_version: { ...draftDoc().current_version, draft_version_id: "v2", created_by: "user", text: "Neu" } }))
      })
    )
    const updated = await updateField("r1", "INTRO.APP.ABSTRACT", "v1", "Neu")
    expect(updated.current_version.created_by).toBe("user")
    expect(body!.base_version_id).toBe("v1")
    expect(csrf).toBe("tok")
  })

  it("maps 409 conflict to a FieldError", async () => {
    server.use(
      http.patch("/api/runs/r1/fields/INTRO.APP.ABSTRACT", () =>
        HttpResponse.json({ code: "stale_base_version" }, { status: 409 })
      )
    )
    let caught: FieldError | null = null
    try {
      await updateField("r1", "INTRO.APP.ABSTRACT", "stale", "x")
    } catch (e) {
      caught = e as FieldError
    }
    expect(caught?.status).toBe(409)
    expect(caught?.code).toBe("stale_base_version")
  })

  it("maps 422 character limit to a FieldError", async () => {
    server.use(
      http.patch("/api/runs/r1/fields/INTRO.APP.ABSTRACT", () =>
        HttpResponse.json({ code: "character_limit_exceeded" }, { status: 422 })
      )
    )
    let caught: FieldError | null = null
    try {
      await updateField("r1", "INTRO.APP.ABSTRACT", "v1", "x".repeat(400))
    } catch (e) {
      caught = e as FieldError
    }
    expect(caught?.status).toBe(422)
  })

  it("createEvidenceLink sends Idempotency-Key", async () => {
    let key: string | null = null
    server.use(
      http.post("/api/runs/r1/fields/INTRO.APP.ABSTRACT/evidence-links", ({ request }) => {
        key = request.headers.get("idempotency-key")
        return HttpResponse.json(
          { evidence_link_id: "l1", anchor_id: "an1", target_type: "draft_version", target_id: "v1", status: "active", created_at: new Date().toISOString() },
          { status: 201 }
        )
      })
    )
    const link = await createEvidenceLink("r1", "INTRO.APP.ABSTRACT", "an1", "v1")
    expect(link.status).toBe("active")
    expect((key ?? "").length).toBeGreaterThanOrEqual(8)
  })

  it("advertises drafts capability while review/export stay off", () => {
    expect(MOCK_CAPABILITIES.features.drafts).toBe(true)
    expect(MOCK_CAPABILITIES.features.review).toBe(false)
    expect(MOCK_CAPABILITIES.features.export).toBe(false)
  })
})
