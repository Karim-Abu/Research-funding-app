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
})
