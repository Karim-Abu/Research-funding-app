import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { PublicResearchPanel } from "@/components/quellen/public-research-panel"

const PROJECT = "p1"
const TASK = "task-1"
const RAW = "Wettbewerber für Acme Robotics AG mit Budget CHF 500'000"
const SANITIZED = "Wettbewerber für mit Budget"

function previewHandler(decision: "require_human_approval" | "block") {
  return http.post(
    `/api/projects/${PROJECT}/search-query-firewall/preview`,
    () =>
      HttpResponse.json({
        data_class: "D2_CONFIDENTIAL_IDEA",
        decision,
        risk_label: decision === "block" ? "high" : "medium",
        sanitized_query: decision === "block" ? "" : SANITIZED,
        redaction_summary:
          decision === "block"
            ? []
            : [
                { category: "partner_name", label: "Partnername", count: 1 },
                { category: "budget_amount", label: "Budget-/Finanzangabe", count: 1 },
              ],
        reasons: [decision],
        approval_id: decision === "block" ? null : "appr-1",
      })
  )
}

function runHandlers(captured: { body?: Record<string, unknown> }) {
  return [
    http.post(`/api/search-query-approvals/appr-1/approve`, () =>
      HttpResponse.json({
        approval_id: "appr-1",
        status: "approved",
        decision: "require_human_approval",
        risk_label: "medium",
        sanitized_query: SANITIZED,
        redaction_summary: [],
      })
    ),
    http.post(`/api/projects/${PROJECT}/research-tasks`, async ({ request }) => {
      captured.body = (await request.json()) as Record<string, unknown>
      return HttpResponse.json(
        {
          operation_id: "op-1",
          resource_type: "research_task",
          resource_id: TASK,
          status: "queued",
          poll_url: "/api/v1/operations/op-1",
        },
        { status: 202 }
      )
    }),
    http.get("/api/operations/op-1", () =>
      HttpResponse.json({
        operation_id: "op-1",
        resource_type: "research_task",
        resource_id: TASK,
        status: "succeeded",
        created_at: new Date().toISOString(),
      })
    ),
    http.get(`/api/projects/${PROJECT}/research-results`, () =>
      HttpResponse.json([
        {
          result_id: "res-1",
          task_id: TASK,
          source_url: "https://research.example.org/result/0",
          title: "Öffentliche Quelle 1",
          snippet: "Auszug",
          accessed_at: new Date().toISOString(),
          status: "candidate",
          professional_evidence: [],
          partner_role_suggestions: [],
          identity_match_status: "not_applicable",
        },
      ])
    ),
  ]
}

function enterAndPreview() {
  fireEvent.change(screen.getByLabelText(/Öffentlicher Suchbegriff/), {
    target: { value: RAW },
  })
  fireEvent.click(screen.getByRole("button", { name: "Vor Webrecherche prüfen" }))
}

describe("PublicResearchPanel — Search Query Firewall (D2)", () => {
  it("shows the confidentiality warning and a 'prüfen' button for D2", () => {
    render(<PublicResearchPanel projectId={PROJECT} dataClass="confidential" />)
    expect(
      screen.getByText(/möglicherweise vertrauliche Angaben/)
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Vor Webrecherche prüfen" })
    ).toBeInTheDocument()
  })

  it("previews a sanitized query and requires approval", async () => {
    server.use(previewHandler("require_human_approval"))
    render(<PublicResearchPanel projectId={PROJECT} dataClass="confidential" />)
    enterAndPreview()
    await waitFor(() =>
      expect(screen.getByTestId("firewall-preview")).toBeInTheDocument()
    )
    expect(screen.getByTestId("sanitized-query")).toHaveTextContent(SANITIZED)
    // The removed categories are shown, but never the raw partner/budget value.
    expect(screen.getByText("Partnername")).toBeInTheDocument()
    expect(screen.getByTestId("firewall-preview")).not.toHaveTextContent("Acme")
    expect(screen.getByTestId("firewall-preview")).not.toHaveTextContent("500")
    expect(
      screen.getByRole("button", { name: "Bereinigte Anfrage freigeben und suchen" })
    ).toBeInTheDocument()
    // No provider/model names.
    expect(screen.queryByText(/firecrawl|anthropic|provider/i)).toBeNull()
  })

  it("approves and runs the search with the approval id", async () => {
    const captured: { body?: Record<string, unknown> } = {}
    server.use(previewHandler("require_human_approval"), ...runHandlers(captured))
    render(<PublicResearchPanel projectId={PROJECT} dataClass="confidential" />)
    enterAndPreview()
    const approve = await screen.findByRole("button", {
      name: "Bereinigte Anfrage freigeben und suchen",
    })
    fireEvent.click(approve)
    await waitFor(() =>
      expect(screen.getByTestId("research-results")).toBeInTheDocument()
    )
    expect(captured.body?.approval_id).toBe("appr-1")
    // The firewall preview card is gone after completion.
    expect(screen.queryByTestId("firewall-preview")).toBeNull()
  })

  it("shows a block message for a query that cannot be sanitized", async () => {
    server.use(previewHandler("block"))
    render(<PublicResearchPanel projectId={PROJECT} dataClass="confidential" />)
    enterAndPreview()
    await waitFor(() =>
      expect(screen.getByTestId("firewall-blocked")).toBeInTheDocument()
    )
    expect(screen.getByText(/allgemeiner/)).toBeInTheDocument()
    expect(screen.queryByTestId("firewall-preview")).toBeNull()
  })
})
