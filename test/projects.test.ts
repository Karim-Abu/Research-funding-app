import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"
import { login } from "@/lib/session"
import { createProjectFromIntake, listProjects } from "@/lib/projects"
import type { IntakeFormData } from "@/lib/types"

const intake: IntakeFormData = {
  titel: "Alpha",
  projektidee: "An innovation idea.",
  innovationsfeld: "",
  budgetrahmen: "350000",
  vertraulichkeit: "public",
  partner: [],
}

function projectFromBody(body: Record<string, unknown>) {
  const now = new Date().toISOString()
  return {
    project_id: "p1",
    workspace_id: "ws-demo",
    status: "draft",
    created_at: now,
    updated_at: now,
    ...body,
  }
}

describe("projects client (live mode)", () => {
  beforeEach(() => setBackendMode("live"))
  afterEach(() => setBackendMode("mock"))

  it("creates a project with Idempotency-Key + CSRF and the mapped classification", async () => {
    server.use(
      http.post("/api/session", () =>
        HttpResponse.json({
          user: {
            user_id: "u1",
            name: "Anna",
            email: "anna.keller@example.test",
            effective_role: "lead_admin",
          },
          csrf_token: "tok",
        })
      )
    )
    await login("anna.keller@example.test", "pw")

    let headers: Headers | null = null
    let body: Record<string, unknown> = {}
    server.use(
      http.post("/api/projects", async ({ request }) => {
        headers = request.headers
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(projectFromBody(body), { status: 201 })
      })
    )

    const project = await createProjectFromIntake(intake)
    expect(project.project_id).toBe("p1")
    expect(headers!.get("x-csrf-token")).toBe("tok")
    const idem = headers!.get("idempotency-key") ?? ""
    expect(idem.length).toBeGreaterThanOrEqual(8)
    expect(body.data_classification).toEqual({
      sensitivity: "public",
      origin: "synthetic",
      processing_mode: "cloud_assisted",
      web_research_mode: "validated_public",
      nda_applies: false,
    })
    expect(body.budget_framework_chf).toBe(350000)
  })

  it("lists projects", async () => {
    server.use(
      http.get("/api/projects", () =>
        HttpResponse.json({
          items: [
            projectFromBody({
              title: "Alpha",
              description: "d",
              funding_instrument_profile_id: "f",
              data_classification: {
                sensitivity: "public",
                origin: "synthetic",
                processing_mode: "cloud_assisted",
                web_research_mode: "validated_public",
                nda_applies: false,
              },
            }),
          ],
          next_cursor: null,
        })
      )
    )
    const items = await listProjects()
    expect(items).toHaveLength(1)
    expect(items[0].title).toBe("Alpha")
  })
})
