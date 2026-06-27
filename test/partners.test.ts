import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"
import { login } from "@/lib/session"
import {
  listPartners,
  createPartner,
  deletePartner,
  PartnerError,
} from "@/lib/partners"

function partnerDoc(overrides: Record<string, unknown> = {}) {
  return {
    partner_id: "pa1",
    project_id: "p1",
    name: "ETH Zürich",
    partner_type: "research_partner",
    country: "CH",
    research_partner_eligibility_status: "eligible",
    ...overrides,
  }
}

describe("partner client (live)", () => {
  beforeEach(() => setBackendMode("live"))
  afterEach(() => setBackendMode("mock"))

  it("lists partners for a project", async () => {
    server.use(
      http.get("/api/projects/p1/partners", () =>
        HttpResponse.json([partnerDoc()])
      )
    )
    const partners = await listPartners("p1")
    expect(partners).toHaveLength(1)
    expect(partners[0].partner_type).toBe("research_partner")
  })

  it("createPartner sends CSRF + Idempotency-Key", async () => {
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
      http.post("/api/projects/p1/partners", ({ request }) => {
        headers = request.headers
        return HttpResponse.json(partnerDoc(), { status: 201 })
      })
    )
    const created = await createPartner("p1", {
      name: "ETH Zürich",
      partner_type: "research_partner",
      country: "CH",
      research_partner_eligibility_status: "eligible",
    })
    expect(created.partner_id).toBe("pa1")
    expect(headers!.get("x-csrf-token")).toBe("tok")
    expect((headers!.get("idempotency-key") ?? "").length).toBeGreaterThanOrEqual(8)
  })

  it("deletePartner tolerates 204", async () => {
    server.use(
      http.delete("/api/partners/pa1", () => new HttpResponse(null, { status: 204 }))
    )
    await expect(deletePartner("pa1")).resolves.toBeUndefined()
  })

  it("maps 404 to a user-safe PartnerError", async () => {
    server.use(
      http.get("/api/projects/missing/partners", () =>
        HttpResponse.json({ code: "not_found" }, { status: 404 })
      )
    )
    let caught: PartnerError | null = null
    try {
      await listPartners("missing")
    } catch (e) {
      caught = e as PartnerError
    }
    expect(caught?.status).toBe(404)
    expect(caught?.message).toContain("nicht gefunden")
  })
})
