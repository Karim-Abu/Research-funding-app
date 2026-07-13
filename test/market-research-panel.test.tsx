import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
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
    // R8 Freigabepflicht: jede Query bringt eine pending Freigabe mit.
    queries: [
      { query_text: "ICT Industrial AI market size Schweiz", purpose: "market_size", public_safe: true, approval_required: true, approval_id: "appr-1" },
      { query_text: "Industrial AI ICT competitors alternatives", purpose: "competitors_alternatives", public_safe: true, approval_required: true, approval_id: "appr-2" },
      { query_text: "ICT quality challenges pain points", purpose: "customer_pain", public_safe: true, approval_required: true, approval_id: "appr-3" },
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

function approvalHandlers() {
  return [
    http.post("/api/search-query-approvals/:id/approve", ({ params }) =>
      HttpResponse.json({ approval_id: params.id, status: "approved" })
    ),
    http.post("/api/search-query-approvals/:id/reject", ({ params }) =>
      HttpResponse.json({ approval_id: params.id, status: "rejected" })
    ),
  ]
}

function runHandler(onBody?: (body: unknown) => void) {
  return http.post(`/api/projects/${PROJECT}/market-research/run`, async ({ request }) => {
    onBody?.(await request.json())
    return HttpResponse.json(runResponse())
  })
}

async function openReview() {
  render(<MarketResearchPanel projectId={PROJECT} />)
  fireEvent.click(screen.getByRole("button", { name: "Marktanalyse vorbereiten" }))
  await waitFor(() => expect(screen.getByTestId("market-research-review")).toBeInTheDocument())
}

async function approveFirstQuery() {
  const rows = screen.getAllByTestId("query-approval-row")
  fireEvent.click(within(rows[0]).getByRole("button", { name: /Freigeben/ }))
  await waitFor(() =>
    expect(within(rows[0]).getByText("Freigegeben")).toBeInTheDocument()
  )
}

describe("MarketResearchPanel", () => {
  it("empty state: shows the action button and the fixed safety notice", () => {
    render(<MarketResearchPanel projectId={PROJECT} />)
    expect(screen.getByTestId("market-research-empty")).toBeInTheDocument()
    expect(
      screen.getByText(/Research-Ergebnisse sind Quellenkandidaten, keine bestätigten Fakten/)
    ).toBeInTheDocument()
  })

  it("query preview: shows the suggested topic and per-query approval actions", async () => {
    server.use(planHandler())
    await openReview()
    expect(screen.getByDisplayValue("ICT")).toBeInTheDocument()
    expect(screen.getByDisplayValue("Industrial AI")).toBeInTheDocument()
    const rows = screen.getAllByTestId("query-approval-row")
    expect(rows.length).toBeGreaterThanOrEqual(3)
    // R8: jede ausgehende Query ist sichtbar und einzeln entscheidbar.
    expect(within(rows[0]).getByRole("button", { name: /Freigeben/ })).toBeInTheDocument()
    expect(within(rows[0]).getByRole("button", { name: /Ablehnen/ })).toBeInTheDocument()
    expect(within(rows[0]).getByRole("button", { name: /Bearbeiten/ })).toBeInTheDocument()
    expect(screen.getByText(/Test-Modus \(Fake\)/)).toBeInTheDocument()
  })

  it("R8: without any approval the run button is disabled with an explanation", async () => {
    server.use(planHandler())
    await openReview()
    expect(screen.getByRole("button", { name: "Recherche starten" })).toBeDisabled()
    expect(
      screen.getByText(/Geben Sie mindestens eine Suchanfrage frei/)
    ).toBeInTheDocument()
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
          { query_text: "Photonik Sensorik market size Schweiz", purpose: "market_size", public_safe: true, approval_required: true, approval_id: "appr-9" },
        ],
      })
    )
    fireEvent.change(screen.getByLabelText("Anwendungsbereich"), { target: { value: "Photonik" } })
    fireEvent.click(screen.getByRole("button", { name: "Vorschau aktualisieren" }))
    await waitFor(() =>
      expect(screen.getByText("Photonik Sensorik market size Schweiz")).toBeInTheDocument()
    )
  })

  it("running research sends ONLY the approved queries and shows candidate cards", async () => {
    let body: unknown = null
    server.use(planHandler(), ...approvalHandlers(), runHandler((b) => { body = b }))
    await openReview()
    await approveFirstQuery()
    fireEvent.click(screen.getByRole("button", { name: "Recherche starten" }))
    await waitFor(() => expect(screen.getByTestId("market-research-results")).toBeInTheDocument())
    expect((body as { approval_ids: string[] }).approval_ids).toEqual(["appr-1"])
    const card = screen.getByTestId("market-candidate-card")
    expect(card).toHaveTextContent("Öffentliche Quelle 1")
    expect(card).toHaveTextContent("Kandidat — menschliche Prüfung nötig")
    expect(card).toHaveTextContent("Confidence: mittel")
  })

  it("'Als Quelle speichern' imports the candidate and shows a saved badge", async () => {
    let imported = false
    server.use(
      planHandler(),
      ...approvalHandlers(),
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
    await approveFirstQuery()
    fireEvent.click(screen.getByRole("button", { name: "Recherche starten" }))
    const importBtn = await screen.findByRole("button", { name: "Als Quelle speichern" })
    fireEvent.click(importBtn)
    await waitFor(() => expect(screen.getByText("Als Quelle gespeichert")).toBeInTheDocument())
    expect(imported).toBe(true)
  })

  it("R8: 'Verwerfen' persists the discard and hides the candidate", async () => {
    let discarded = false
    server.use(
      planHandler(),
      ...approvalHandlers(),
      runHandler(),
      http.post("/api/research-results/res-1/discard", () => {
        discarded = true
        return HttpResponse.json({
          result_id: "res-1", task_id: "t1",
          source_url: "https://research.example.org/result/0",
          title: "Öffentliche Quelle 1", snippet: "Auszug (kein Beleg)",
          accessed_at: new Date().toISOString(), status: "rejected",
          professional_evidence: [], partner_role_suggestions: [],
          identity_match_status: "not_applicable",
        })
      })
    )
    await openReview()
    await approveFirstQuery()
    fireEvent.click(screen.getByRole("button", { name: "Recherche starten" }))
    const card = await screen.findByTestId("market-candidate-card")
    fireEvent.click(within(card).getByRole("button", { name: "Verwerfen" }))
    await waitFor(() =>
      expect(screen.queryByTestId("market-candidate-card")).toBeNull()
    )
    expect(discarded).toBe(true)
  })

  it("a blocked run (403) shows a clear error plus the manual fallback", async () => {
    server.use(
      planHandler(),
      ...approvalHandlers(),
      http.post(`/api/projects/${PROJECT}/market-research/run`, () =>
        HttpResponse.json({ code: "web_research_class_blocked" }, { status: 403 })
      )
    )
    await openReview()
    await approveFirstQuery()
    fireEvent.click(screen.getByRole("button", { name: "Recherche starten" }))
    await waitFor(() =>
      expect(screen.getByText(/gesperrt|Fehler/)).toBeInTheDocument()
    )
    // No dead end: the review form (with retry) AND the manual fallback remain.
    expect(screen.getByTestId("market-research-review")).toBeInTheDocument()
    expect(screen.getByTestId("market-research-fallback")).toBeInTheDocument()
    expect(screen.getByText("Quelle manuell hinzufügen")).toBeInTheDocument()
  })

  it("provider unavailable: shows the guided manual fallback instead of a dead end", async () => {
    server.use(planHandler({ provider_mode: "unavailable" }), ...approvalHandlers())
    await openReview()
    expect(screen.getByTestId("market-research-fallback")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Recherche starten" })).toBeDisabled()
  })

  it("never renders provider/canary/secret terminology", async () => {
    server.use(planHandler(), ...approvalHandlers(), runHandler())
    await openReview()
    await approveFirstQuery()
    fireEvent.click(screen.getByRole("button", { name: "Recherche starten" }))
    await waitFor(() => expect(screen.getByTestId("market-research-results")).toBeInTheDocument())
    expect(screen.queryByText(/firecrawl|api[_ ]?key|token/i)).toBeNull()
  })
})
