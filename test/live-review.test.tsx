import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { LiveReview } from "@/components/review/live-review"

function pkg(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "r1",
    requirements: [],
    fields: [],
    findings: [],
    approval_status: "blocked",
    blocker_count: 0,
    warning_count: 0,
    open_issues: [],
    review_package_version: "rpv-1",
    current_approval_scope_hash: "a".repeat(64),
    recheck_required: false,
    stale_finding_count: 0,
    ...overrides,
  }
}

describe("LiveReview", () => {
  it("shows blocker findings and disables approval with reasons", async () => {
    server.use(
      http.get("/api/runs/r1/review", () =>
        HttpResponse.json(
          pkg({
            blocker_count: 1,
            findings: [
              {
                finding_id: "f1",
                profile_id: "p",
                field_id: "INTRO.APP.ABSTRACT",
                requirement_id: null,
                severity: "blocker",
                description: "Feld enthält Platzhalter.",
                suggested_improvement: null,
                status: "open",
                advisory: false,
              },
            ],
          })
        )
      )
    )
    render(<LiveReview runId="r1" />)
    await waitFor(() =>
      expect(screen.getByText("Feld enthält Platzhalter.")).toBeInTheDocument()
    )
    const approve = screen.getByRole("button", { name: /Review freigeben/ })
    expect(approve).toBeDisabled()
    expect(screen.getByText(/1 Blocker offen/)).toBeInTheDocument()
  })

  it("enables approval when clean and shows recheck notice when required", async () => {
    server.use(
      http.get("/api/runs/r1/review", () =>
        HttpResponse.json(pkg({ recheck_required: true, approval_status: "blocked" }))
      )
    )
    render(<LiveReview runId="r1" />)
    await waitFor(() =>
      expect(
        screen.getByText(/ungeprüfte Änderungen/)
      ).toBeInTheDocument()
    )
    // recheck_required blocks approval.
    expect(screen.getByRole("button", { name: /Review freigeben/ })).toBeDisabled()
    expect(screen.getByText(/Erneute Prüfung erforderlich/)).toBeInTheDocument()
  })

  it("approves successfully when no blockers remain", async () => {
    server.use(
      http.get("/api/runs/r1/review", () =>
        HttpResponse.json(pkg({ approval_status: "open" }))
      ),
      http.post("/api/runs/r1/approvals", () =>
        HttpResponse.json(
          {
            approval_id: "ap1",
            run_id: "r1",
            scope: "run",
            status: "approved",
            approval_scope_hash: "a".repeat(64),
            approved_by: "u",
            created_at: new Date().toISOString(),
          },
          { status: 201 }
        )
      )
    )
    render(<LiveReview runId="r1" />)
    const approve = await screen.findByRole("button", { name: /Review freigeben/ })
    expect(approve).toBeEnabled()
    fireEvent.click(approve)
    await waitFor(() =>
      expect(screen.getByText("Review freigegeben.")).toBeInTheDocument()
    )
  })

  it("shows the Nächste Schritte card with derived actions (M10.2)", async () => {
    server.use(
      http.get("/api/runs/r1/review", () =>
        HttpResponse.json(
          pkg({
            recheck_required: true,
            blocker_count: 1,
            findings: [
              {
                finding_id: "f1",
                profile_id: "p",
                field_id: "INTRO.APP.ABSTRACT",
                requirement_id: null,
                severity: "blocker",
                description: "Feld enthält Platzhalter.",
                suggested_improvement: null,
                status: "open",
                advisory: false,
              },
            ],
          })
        )
      )
    )
    render(<LiveReview runId="r1" />)
    const card = await screen.findByTestId("next-steps")
    expect(card).toHaveTextContent("Nächste Schritte")
    expect(card).toHaveTextContent(/Ungeprüfte Änderungen/)
    expect(card).toHaveTextContent(/Platzhalter/)
    // The M10.1 stale-reliability banner stays untouched and absent here.
    expect(screen.queryByTestId("reliability-stale-banner")).toBeNull()
  })

  it("shows the stale-reliability banner and blocks approval (M10.1, F3)", async () => {
    server.use(
      http.get("/api/runs/r1/review", () =>
        HttpResponse.json(
          pkg({
            blocker_count: 1,
            findings: [
              {
                finding_id: "rel-stale", profile_id: "M9K.reliability_assurance",
                field_id: null, requirement_id: null,
                severity: "blocker",
                description:
                  "Qualitätsprüfung veraltet: der Entwurf wurde nach dem letzten " +
                  "Reliability-Lauf geändert.",
                suggested_improvement: null, status: "open", advisory: false,
              },
            ],
          })
        )
      )
    )
    render(<LiveReview runId="r1" />)
    const banner = await screen.findByTestId("reliability-stale-banner")
    expect(banner).toHaveTextContent(
      "Qualitätsprüfung veraltet — bitte erneut ausführen."
    )
    expect(screen.getByRole("button", { name: /Review freigeben/ })).toBeDisabled()
  })

  it("shows no stale-reliability banner for claim-bound reliability findings", async () => {
    server.use(
      http.get("/api/runs/r1/review", () =>
        HttpResponse.json(
          pkg({
            blocker_count: 1,
            findings: [
              {
                finding_id: "rel-claim", profile_id: "M9K.reliability_assurance",
                field_id: "SOL.INNOVATION_SOLUTION.EDITOR", requirement_id: null,
                severity: "blocker",
                description: "Nicht belegte Aussage: bitte belegen oder abschwächen.",
                suggested_improvement: null, status: "open", advisory: false,
              },
            ],
          })
        )
      )
    )
    render(<LiveReview runId="r1" />)
    await waitFor(() =>
      expect(
        screen.getAllByText(/Nicht belegte Aussage/).length
      ).toBeGreaterThan(0)
    )
    expect(screen.queryByTestId("reliability-stale-banner")).toBeNull()
  })

  it("groups A3 findings under KI-gestützte Hinweise, blocks approval, hides provider", async () => {
    server.use(
      http.get("/api/runs/r1/review", () =>
        HttpResponse.json(
          pkg({
            blocker_count: 1,
            findings: [
              {
                finding_id: "det1", profile_id: "deterministic-review-1",
                field_id: "INTRO.APP.ABSTRACT", requirement_id: null,
                severity: "warning", description: "Deterministischer Hinweis.",
                suggested_improvement: null, status: "open", advisory: true,
              },
              {
                finding_id: "ai1", profile_id: "A3.evidence_consistency",
                field_id: "SOL.INNOVATION_SOLUTION.EDITOR", requirement_id: null,
                severity: "blocker",
                description: "Aussage ohne verifizierten Beleg.",
                suggested_improvement: "Beleg verknüpfen oder offen markieren.",
                status: "open", advisory: false,
              },
            ],
          })
        )
      )
    )
    render(<LiveReview runId="r1" />)
    const aiSection = await screen.findByTestId("ai-findings")
    expect(aiSection).toHaveTextContent("KI-gestützte Hinweise")
    expect(aiSection).toHaveTextContent("Aussage ohne verifizierten Beleg.")
    // Deterministic finding stays out of the KI section.
    expect(aiSection).not.toHaveTextContent("Deterministischer Hinweis.")
    // A3 blocker disables approval.
    expect(screen.getByRole("button", { name: /Review freigeben/ })).toBeDisabled()
    // No model/provider/confidence leaks anywhere.
    expect(screen.queryByText(/anthropic|openai|gpt|claude|sonnet|confidence|Konfidenz/i)).toBeNull()
  })
})
