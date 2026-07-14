import { describe, expect, it } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"

import { PublicResearchPanel } from "@/components/quellen/public-research-panel"
import { server } from "./server"

const PROJECT = "p1"
const BRIEF = {
  research_brief_id: "brief-1", version: 1, status: "approved",
  application_domain: "industrial quality", technology_class: "anomaly detection",
  target_customer_segments: ["manufacturing SMEs"], region: "Switzerland",
  competence_needs: [], modules: ["market_growth"],
  approved_at: "2026-07-14T08:00:00Z",
}
const SANITIZED = "industrial quality anomaly detection market size Switzerland"

function workspace(status: "pending" | "approved" | "expired" = "pending") {
  return {
    brief: { latest: BRIEF, active_approved: BRIEF },
    provider_mode: "fake_demo",
    results: [],
    queries: [{
      approval_id: "approval-1", research_brief_id: "brief-1",
      module: "market_growth", planner_purpose: "market_size",
      query_text: SANITIZED, firewall_decision: "require_human_approval",
      risk_label: "medium",
      redaction_summary: [
        { category: "partner_name", label: "Partnername", count: 1 },
        { category: "budget_amount", label: "Budget-/Finanzangabe", count: 1 },
      ],
      status, task_id: null, task_status: null, execution_mode: null,
    }],
  }
}

describe("PublicResearchPanel — Search Query Firewall (D2)", () => {
  it("shows only the persisted sanitized query and safe redaction categories", async () => {
    server.use(http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(workspace())))
    render(<PublicResearchPanel projectId={PROJECT} dataClass="confidential" />)
    expect(await screen.findByText(SANITIZED)).toBeInTheDocument()
    expect(screen.getByText(/Firewall: menschliche Freigabe nötig/)).toBeInTheDocument()
    expect(screen.getByText("Partnername (1)")).toBeInTheDocument()
    expect(screen.getByText("Budget-/Finanzangabe (1)")).toBeInTheDocument()
    expect(screen.queryByText(/Acme Robotics|500'000/)).toBeNull()
    expect(screen.queryByText(/firecrawl|anthropic|provider/i)).toBeNull()
  })

  it("persists human approval and enables only the approved query", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(workspace())),
      http.post("/api/search-query-approvals/approval-1/approve", () => HttpResponse.json({
        approval_id: "approval-1", status: "approved",
      })),
    )
    render(<PublicResearchPanel projectId={PROJECT} dataClass="confidential" />)
    fireEvent.click(await screen.findByRole("button", { name: "Freigeben" }))
    expect(await screen.findByText("1 von 1 Suchanfragen freigegeben")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Freigegebene Queries ausführen/ })).toBeEnabled()
  })

  it("edits through the brief-bound preview and invalidates the old approval", async () => {
    let rejected = false
    server.use(
      http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(workspace())),
      http.post("/api/research-briefs/brief-1/queries/preview", async ({ request }) => {
        const body = await request.json() as Record<string, unknown>
        expect(body.supersedes_approval_id).toBe("approval-1")
        return HttpResponse.json({
          ...workspace().queries[0], approval_id: "approval-2",
          query_text: "industrial quality market growth Switzerland",
        })
      }),
      http.post("/api/search-query-approvals/approval-1/reject", () => {
        rejected = true
        return HttpResponse.json({ approval_id: "approval-1", status: "expired" })
      }),
    )
    render(<PublicResearchPanel projectId={PROJECT} dataClass="confidential" />)
    fireEvent.click(await screen.findByRole("button", { name: "Bearbeiten" }))
    fireEvent.change(screen.getByLabelText("Suchanfrage bearbeiten"), {
      target: { value: "industrial quality market growth Switzerland" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Prüfen und übernehmen" }))
    expect(await screen.findByText("industrial quality market growth Switzerland")).toBeInTheDocument()
    expect(rejected).toBe(true)
  })

  it("shows a safe error when an edited query introduces unapproved terms", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(workspace())),
      http.post("/api/research-briefs/brief-1/queries/preview", () => HttpResponse.json({
        detail: "Neue Fachbegriffe müssen zuerst im Recherchebrief geprüft werden.",
      }, { status: 422 })),
    )
    render(<PublicResearchPanel projectId={PROJECT} dataClass="confidential" />)
    fireEvent.click(await screen.findByRole("button", { name: "Bearbeiten" }))
    fireEvent.change(screen.getByLabelText("Suchanfrage bearbeiten"), {
      target: { value: "private codename" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Prüfen und übernehmen" }))
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/konnte nicht geprüft/))
  })
})
