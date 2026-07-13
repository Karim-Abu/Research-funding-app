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
    // R8: verifiziertes Zitat = «Textstelle gefunden» (nie als Fakt dargestellt).
    expect(screen.getByText("Textstelle gefunden")).toBeInTheDocument()
    expect(screen.getByTestId("market-research-gaps")).toHaveTextContent(
      "Marktgröße ist nicht belegt."
    )
    expect(screen.getByText("Offene Evidenzlücken")).toBeInTheDocument()
    // No provider/model/confidence leakage, no automatic "use in draft" action.
    expect(
      screen.queryByText(/anthropic|haiku|firecrawl|confidence|Konfidenz|Für Antrag verwenden/i)
    ).toBeNull()
  })

  it("groups items into the five summary sections and lists used source names", async () => {
    const items = [
      comparison().items[0],
      {
        ...comparison().items[0],
        item_id: "i2",
        name: "Marktwachstum Bericht",
        category: "market_size_claim",
        source_document_ids: ["s2"],
      },
      {
        ...comparison().items[0],
        item_id: "i3",
        name: "Manuelle Prüfung dauert lange",
        category: "customer_problem",
        source_document_ids: ["s1"],
      },
    ]
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(comparison({ items, item_count: 3 }))
      )
    )
    render(
      <MarketComparisonSection
        projectId={PROJECT}
        sourceNames={{ s1: "Marktbericht (öffentlich)", s2: "Branchenstudie" }}
      />
    )
    await waitFor(() =>
      expect(screen.getByTestId("market-comparison-table")).toBeInTheDocument()
    )
    expect(screen.getByText("Marktgrössen-Kandidaten")).toBeInTheDocument()
    expect(screen.getByText("Wettbewerber und Alternativen")).toBeInTheDocument()
    expect(screen.getByText("Kundenprobleme")).toBeInTheDocument()
    const used = screen.getByTestId("market-used-sources")
    expect(used).toHaveTextContent("Verwendete Quellen")
    expect(used).toHaveTextContent("Marktbericht (öffentlich)")
    expect(used).toHaveTextContent("Branchenstudie")
    // Nie rohe IDs in der Standard-UI.
    expect(used).not.toHaveTextContent("s1")
  })

  it("shows «Inhaltlich geprüft» after human acceptance instead of the quote status", async () => {
    const accepted = comparison({
      items: [{ ...comparison().items[0], status: "accepted" }],
    })
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(accepted)
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    await waitFor(() =>
      expect(screen.getByText("Inhaltlich geprüft")).toBeInTheDocument()
    )
    expect(screen.queryByText("Textstelle gefunden")).toBeNull()
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
