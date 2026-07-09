import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { MarketResearchPanel } from "@/components/editor/market-research-panel"

const PROJECT = "p1"

function planResponse(overrides: Record<string, unknown> = {}) {
  return {
    topic: {
      application_domain: "ICT",
      technology_area: "Industrial AI",
      target_customers: "Unternehmen und Organisationen in der Schweiz",
      region: "Schweiz",
    },
    queries: [
      { query_text: "ICT Industrial AI market size Schweiz", purpose: "market_size", public_safe: true, approval_required: false },
      { query_text: "Industrial AI ICT competitors alternatives", purpose: "competitors_alternatives", public_safe: true, approval_required: false },
      { query_text: "ICT quality challenges pain points", purpose: "customer_pain", public_safe: true, approval_required: false },
    ],
    provider_mode: "fake",
    ...overrides,
  }
}

function runResponse() {
  return {
    task_ids: ["t1"],
    result_count: 1,
    tool_invocation_count: 2,
    credits_used: 0,
    blocked_queries: 0,
    provider: "fake",
    candidates: [
      {
        result_id: "res-1",
        purpose: "market_size",
        candidate_type: "market_size_candidate",
        title: "Öffentliche Quelle 1",
        source_url: "https://research.example.org/result/0",
        snippet: "Auszug (kein Beleg)",
        confidence: "medium",
        status: "candidate",
        human_review_required: true,
      },
    ],
  }
}

function planHandler(overrides: Record<string, unknown> = {}) {
  return http.post(`/api/projects/${PROJECT}/market-research/plan`, () =>
    HttpResponse.json(planResponse(overrides))
  )
}

function runHandler() {
  return http.post(`/api/projects/${PROJECT}/market-research/run`, () =>
    HttpResponse.json(runResponse())
  )
}

async function openReview() {
  render(<MarketResearchPanel projectId={PROJECT} />)
  fireEvent.click(screen.getByRole("button", { name: "Marktanalyse vorbereiten" }))
  await waitFor(() => expect(screen.getByTestId("market-research-review")).toBeInTheDocument())
}

describe("MarketResearchPanel", () => {
  it("empty state: shows the action button and the fixed safety notice", () => {
    render(<MarketResearchPanel projectId={PROJECT} />)
    expect(screen.getByTestId("market-research-empty")).toBeInTheDocument()
    expect(
      screen.getByText(/Research-Ergebnisse sind Quellenkandidaten, keine bestätigten Fakten/)
    ).toBeInTheDocument()
  })

  it("query preview: shows the suggested topic and 3-5 public-safe query candidates", async () => {
    server.use(planHandler())
    await openReview()
    expect(screen.getByDisplayValue("ICT")).toBeInTheDocument()
    expect(screen.getByDisplayValue("Industrial AI")).toBeInTheDocument()
    const queries = screen.getAllByText(/market size|competitors alternatives|pain points/)
    expect(queries.length).toBeGreaterThanOrEqual(3)
    expect(screen.getByText(/Test-Modus \(Fake\)/)).toBeInTheDocument()
  })

  it("editing a topic field and refreshing recomputes the preview", async () => {
    server.use(planHandler())
    await openReview()
    server.use(
      planHandler({
        topic: {
          application_domain: "Photonik",
          technology_area: "Sensorik",
          target_customers: "Unternehmen und Organisationen in der Schweiz",
          region: "Schweiz",
        },
        queries: [
          { query_text: "Photonik Sensorik market size Schweiz", purpose: "market_size", public_safe: true, approval_required: false },
        ],
      })
    )
    fireEvent.change(screen.getByLabelText("Anwendungsbereich"), { target: { value: "Photonik" } })
    fireEvent.click(screen.getByRole("button", { name: "Vorschau aktualisieren" }))
    await waitFor(() =>
      expect(screen.getByText("Photonik Sensorik market size Schweiz")).toBeInTheDocument()
    )
  })

  it("running research shows results as candidate cards with a human-review badge", async () => {
    server.use(planHandler(), runHandler())
    await openReview()
    fireEvent.click(screen.getByRole("button", { name: "Recherche starten" }))
    await waitFor(() => expect(screen.getByTestId("market-research-results")).toBeInTheDocument())
    const card = screen.getByTestId("market-candidate-card")
    expect(card).toHaveTextContent("Öffentliche Quelle 1")
    expect(card).toHaveTextContent("Kandidat — menschliche Prüfung nötig")
    expect(card).toHaveTextContent("Confidence: mittel")
  })

  it("'Als Quelle speichern' imports the candidate and shows a saved badge", async () => {
    let imported = false
    server.use(
      planHandler(),
      runHandler(),
      http.post("/api/research-results/res-1/import", () => {
        imported = true
        return HttpResponse.json(
          {
            source_id: "s1", project_id: PROJECT, name: "Öffentliche Quelle 1", type: "url",
            status: "processed",
            data_classification: {
              sensitivity: "public", origin: "public_source", processing_mode: "deterministic_only",
              web_research_mode: "validated_public", nda_applies: false,
            },
          },
          { status: 201 }
        )
      })
    )
    await openReview()
    fireEvent.click(screen.getByRole("button", { name: "Recherche starten" }))
    const importBtn = await screen.findByRole("button", { name: "Als Quelle speichern" })
    fireEvent.click(importBtn)
    await waitFor(() => expect(screen.getByText("Als Quelle gespeichert")).toBeInTheDocument())
    expect(imported).toBe(true)
  })

  it("a blocked run (403) shows a clear error instead of crashing", async () => {
    server.use(
      planHandler(),
      http.post(`/api/projects/${PROJECT}/market-research/run`, () =>
        HttpResponse.json({ code: "web_research_class_blocked" }, { status: 403 })
      )
    )
    await openReview()
    fireEvent.click(screen.getByRole("button", { name: "Recherche starten" }))
    await waitFor(() =>
      expect(screen.getByText(/gesperrt|Fehler/)).toBeInTheDocument()
    )
    // No dead end: the review form (with retry) remains visible.
    expect(screen.getByTestId("market-research-review")).toBeInTheDocument()
  })

  it("never renders provider/canary/secret terminology", async () => {
    server.use(planHandler(), runHandler())
    await openReview()
    fireEvent.click(screen.getByRole("button", { name: "Recherche starten" }))
    await waitFor(() => expect(screen.getByTestId("market-research-results")).toBeInTheDocument())
    expect(screen.queryByText(/firecrawl|api[_ ]?key|token/i)).toBeNull()
  })
})
