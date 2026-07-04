import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { MarketComparisonSection } from "@/components/quellen/market-comparison-section"

const PROJECT = "p1"

function comparison(overrides: Record<string, unknown> = {}) {
  return {
    comparison_id: "c1",
    project_id: PROJECT,
    status: "ready_for_review",
    comparison_version: 1,
    generation_status: "succeeded",
    research_gaps: ["Marktgröße ist nicht belegt."],
    warnings: [],
    item_count: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    items: [
      {
        item_id: "i1",
        name: "Acme Plattform",
        category: "alternative_solution",
        description: "Eine öffentlich erwähnte Lösung.",
        target_customer_segment: null,
        offering_summary: null,
        strengths: null,
        weaknesses: null,
        differentiation_relevance: "Hinweis aus öffentlicher Quelle.",
        relation_to_project: "competing",
        confidence_label: "source_backed",
        status: "proposed",
        source_document_ids: ["s1"],
        evidence_quotes: [
          {
            quote: "Acme ist eine alternative Lösung für den Markt.",
            source_document_id: "s1",
            source_version_id: "v1",
            linked_evidence_anchor_id: null,
          },
        ],
      },
    ],
    ...overrides,
  }
}

describe("MarketComparisonSection", () => {
  it("renders the comparison table, quote, status label and research gaps", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(comparison())
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    await waitFor(() =>
      expect(screen.getByTestId("market-comparison-table")).toBeInTheDocument()
    )
    expect(screen.getByText("Acme Plattform")).toBeInTheDocument()
    expect(
      screen.getByText(/Acme ist eine alternative Lösung/)
    ).toBeInTheDocument()
    expect(screen.getByText("Quelle erwähnt")).toBeInTheDocument()
    expect(screen.getByTestId("market-research-gaps")).toHaveTextContent(
      "Marktgröße ist nicht belegt."
    )
    // No provider/model/confidence leakage, no automatic "use in draft" action.
    expect(
      screen.queryByText(/anthropic|haiku|firecrawl|confidence|Konfidenz|Für Antrag verwenden/i)
    ).toBeNull()
  })

  it("shows an empty state when no comparison exists", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(null)
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    await waitFor(() =>
      expect(screen.getByText(/Noch kein Vergleich/)).toBeInTheDocument()
    )
    expect(
      screen.getByRole("button", { name: "Vergleich erstellen" })
    ).toBeInTheDocument()
  })

  it("generates a comparison and renders the result", async () => {
    let created = false
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(created ? comparison() : null)
      ),
      http.post(`/api/projects/${PROJECT}/market-comparisons`, () =>
        HttpResponse.json(
          {
            operation_id: "op1",
            resource_type: "market_comparison",
            resource_id: "c1",
            status: "queued",
            poll_url: "/api/v1/operations/op1",
          },
          { status: 202 }
        )
      ),
      http.get("/api/operations/op1", () => {
        created = true
        return HttpResponse.json({
          operation_id: "op1",
          resource_type: "market_comparison",
          resource_id: "c1",
          status: "succeeded",
          created_at: new Date().toISOString(),
        })
      })
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    const btn = await screen.findByRole("button", { name: "Vergleich erstellen" })
    fireEvent.click(btn)
    await waitFor(() =>
      expect(screen.getByTestId("market-comparison-table")).toBeInTheDocument()
    )
    expect(screen.getByText("Acme Plattform")).toBeInTheDocument()
  })
})
