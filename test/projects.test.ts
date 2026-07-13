import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"
import { login } from "@/lib/session"
import {
  archiveProject,
  createProjectFromIntake,
  listProjects,
  toDashboardCard,
} from "@/lib/projects"
import type { IntakeFormData } from "@/lib/types"

const intake: IntakeFormData = {
  titel: "Alpha",
  projektidee: "An innovation idea.",
  innovationsfeld: "",
  vertraulichkeit: "public",
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
    // Budget wird nicht mehr im Intake erfasst — Erfassungsort ist
    // «Partner & Budget» (PATCH /projects).
    expect(body.budget_framework_chf).toBeNull()
  })

  it("rejects intake without confidentiality before sending a create payload", async () => {
    await expect(
      createProjectFromIntake({ ...intake, vertraulichkeit: "" })
    ).rejects.toThrow("confidentiality_missing")
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

  it("maps workflow_summary to dashboard cards", () => {
    const card = toDashboardCard(
      projectFromBody({
        title: "KI-gestuetzte Entwicklung (Demo)",
        description: "d",
        funding_instrument_profile_id: "f",
        data_classification: {
          sensitivity: "public",
          origin: "synthetic",
          processing_mode: "deterministic_only",
          web_research_mode: "off",
          nda_applies: false,
        },
        workflow_summary: {
          bearbeitungsstand_percent: 72,
          current_step: 5,
          current_step_label: "Entwurf",
          next_action: "continue_draft",
          warning_badge: null,
          latest_run_id: "r1",
        },
      })
    )
    expect(card.progressPercent).toBe(72)
    // Backend step 5 (Entwurf) → UI step 4 «Antragsentwurf» (6-Schritte-
    // Katalog, lib/workflow.ts).
    expect(card.currentStep).toBe(4)
    expect(card.nextAction).toBe("continue_draft")
    expect(card.isDemo).toBe(true)
    expect(card.warningBadge).toBeUndefined()
  })

  it("archives a project via PATCH (status archived) with CSRF", async () => {
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
      http.patch("/api/projects/p1", async ({ request }) => {
        headers = request.headers
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(projectFromBody(body), { status: 200 })
      })
    )

    await archiveProject("p1")
    expect(body).toEqual({ status: "archived" })
    expect(headers!.get("x-csrf-token")).toBe("tok")
  })

  it("archiveProject is a no-op in mock mode (no network call)", async () => {
    setBackendMode("mock")
    await expect(archiveProject("p1")).resolves.toBeUndefined()
  })

  it("preserves mock mode by returning no live project data", async () => {
    setBackendMode("mock")
    await expect(listProjects()).resolves.toEqual([])
  })
})
