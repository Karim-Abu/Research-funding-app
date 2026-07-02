import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { LiveExport } from "@/components/export/live-export"

function reviewPkg(status: string) {
  return {
    run_id: "r1",
    requirements: [],
    fields: [],
    findings: [],
    approval_status: status,
    blocker_count: 0,
    warning_count: 0,
    open_issues: [],
    review_package_version: "rpv-1",
    current_approval_scope_hash: "a".repeat(64),
    recheck_required: false,
    stale_finding_count: 0,
  }
}

function mockReview(status: string) {
  server.use(http.get("/api/runs/r1/review", () => HttpResponse.json(reviewPkg(status))))
}

function field(id: string, name: string, text: string, openIssues = 0) {
  return {
    draft_id: `d-${id}`,
    field_id: id,
    field_name: name,
    status: "template",
    current_version: {
      draft_version_id: `v-${id}`,
      draft_id: `d-${id}`,
      text,
      character_count: text.length,
      created_by: "system",
      created_at: new Date().toISOString(),
    },
    character_count: text.length,
    character_limit: 2000,
    open_issue_count: openIssues,
    evidence_links: [],
    open_issues: [],
  }
}

describe("LiveExport", () => {
  it("shows all three cards + the fixed no-submission disclaimer", async () => {
    mockReview("blocked")
    render(<LiveExport runId="r1" />)
    expect(await screen.findByText("Word-Arbeitsdokument")).toBeInTheDocument()
    expect(screen.getByText("Markdown-Zusammenfassung")).toBeInTheDocument()
    expect(screen.getByText("Technischer Nachweis")).toBeInTheDocument()
    expect(
      screen.getByText(/Diese Plattform reicht nichts automatisch ein/)
    ).toBeInTheDocument()
  })

  it("shows the advisory ENTWURF banner + badges when not approved", async () => {
    mockReview("blocked")
    render(<LiveExport runId="r1" />)
    await waitFor(() =>
      expect(screen.getByText(/Noch nicht review-freigegeben/)).toBeInTheDocument()
    )
    expect(screen.getAllByText("ENTWURF").length).toBe(3)
  })

  it("shows the approved banner and no draft badges", async () => {
    mockReview("approved")
    render(<LiveExport runId="r1" />)
    await waitFor(() =>
      expect(
        screen.getByText("Review freigegeben – keine Einreichfreigabe.")
      ).toBeInTheDocument()
    )
    expect(screen.queryByText("ENTWURF")).not.toBeInTheDocument()
  })

  it("shows the Feld-Bereitschaft overview with honest Kopierbereit semantics (M10.2)", async () => {
    server.use(
      http.get("/api/runs/r1/review", () =>
        HttpResponse.json({
          ...reviewPkg("blocked"),
          blocker_count: 1,
          findings: [
            {
              finding_id: "f-ev",
              profile_id: "deterministic-review-1",
              field_id: "SOL.INNOVATION_SOLUTION.EDITOR",
              requirement_id: null,
              severity: "blocker",
              description: "Beleg fehlt für diese Aussage.",
              suggested_improvement: null,
              status: "open",
              advisory: false,
            },
          ],
        })
      ),
      http.get("/api/runs/r1/fields", () =>
        HttpResponse.json([
          field(
            "INTRO.APP.ABSTRACT",
            "Abstract",
            "Sauberer Text ohne offene Angaben."
          ),
          field(
            "VC.BUSINESS_TARGETS_MODEL.EDITOR",
            "Business Targets & Business Model",
            "Text mit [[Angabe ergänzen: Zielmarkt]] Platzhalter."
          ),
          field(
            "SOL.INNOVATION_SOLUTION.EDITOR",
            "Innovation & Lösung",
            "Text ohne Platzhalter, aber mit Beleg-Blocker."
          ),
        ])
      )
    )
    render(<LiveExport runId="r1" />)

    const section = await screen.findByTestId("field-readiness")
    expect(section).toHaveTextContent("Feld-Bereitschaft")
    expect(section).toHaveTextContent("Abstract")
    expect(section).toHaveTextContent("Kopierbereit")
    expect(section).toHaveTextContent("Platzhalter offen")
    expect(section).toHaveTextContent("Beleg fehlt")
    // Honest semantics: legend + explicit non-submission marker.
    expect(section).toHaveTextContent(/keine fachliche Freigabe/)
    expect(section).toHaveTextContent(/Manuell im Portal zu erfassen/)
    expect(screen.getByText("Nicht zur Einreichung")).toBeInTheDocument()
    // technical_evidence stays present, framed as audit artifact.
    expect(screen.getByText("Für Audit/Evaluation")).toBeInTheDocument()
    expect(screen.getByText("Technischer Nachweis")).toBeInTheDocument()
  })

  it("creates an export and uses the returned artifact's draft_marked", async () => {
    vi.useRealTimers()
    mockReview("approved") // banner says approved, but the artifact is authoritative
    server.use(
      http.post("/api/session", () =>
        HttpResponse.json({
          user: { user_id: "u", name: "A", email: "a@x.test", effective_role: "lead_admin" },
          csrf_token: "tok",
        })
      ),
      http.post("/api/runs/r1/exports", () =>
        HttpResponse.json(
          { operation_id: "op1", resource_type: "export", resource_id: "ex1", status: "queued", poll_url: "/api/operations/op1" },
          { status: 202 }
        )
      ),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "export", resource_id: "ex1",
          status: "succeeded", created_at: new Date().toISOString(),
        })
      ),
      http.get("/api/exports/ex1", () =>
        HttpResponse.json({
          export_id: "ex1", run_id: "r1", type: "docx", status: "available",
          draft_marked: true, filename: "Projekt_Arbeitsdokument_ENTWURF.docx",
          created_at: new Date().toISOString(),
        })
      )
    )
    render(<LiveExport runId="r1" />)
    const createBtn = (await screen.findAllByRole("button", { name: "Erstellen" }))[0]
    fireEvent.click(createBtn)
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Bereit zum Herunterladen/ })
      ).toBeInTheDocument()
    )
    // Artifact draft_marked=true → ENTWURF badge appears even though review said approved.
    expect(screen.getByText("Projekt_Arbeitsdokument_ENTWURF.docx")).toBeInTheDocument()
    expect(screen.getByText("ENTWURF")).toBeInTheDocument()
  })
})
