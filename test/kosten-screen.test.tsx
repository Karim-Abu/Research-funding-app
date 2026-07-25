import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { KostenScreen } from "@/components/kosten/kosten-screen"
import { getProjectCosts, type ProjectCostViewDto } from "@/lib/kosten-live"

let mode: "live" | "mock" = "live"
let activeProjectId: string | null = "project-1"

vi.mock("@/components/providers/app-providers", () => ({
  useSession: () => ({ mode }),
}))

vi.mock("@/components/providers/workflow-run-provider", () => ({
  useActiveRun: () => ({ projectId: activeProjectId, loading: false }),
}))

vi.mock("@/lib/kosten-live", async () => {
  const actual = await vi.importActual<typeof import("@/lib/kosten-live")>("@/lib/kosten-live")
  return { ...actual, getProjectCosts: vi.fn() }
})

const mockedGetProjectCosts = vi.mocked(getProjectCosts)

const exact: ProjectCostViewDto = {
  project_id: "project-1",
  billing_currency: "USD",
  chf_reference_source: "https://www.snb.ch/example",
  chf_reference_rate: 0.8065,
  chf_reference_as_of: "2026-07-17",
  runs: [{
    id: "run-1",
    started_at: "2026-07-24T10:00:00Z",
    ended_at: "2026-07-24T10:01:30Z",
    status: "completed",
    processing_mode: "live",
    user: "Anna Keller",
    max_cost_chf: 2,
    input_tokens: 20_000,
    cached_input_tokens: 5_000,
    cache_write_input_tokens: 0,
    output_tokens: 3_000,
    llm_calls: 1,
    web_calls: 0,
    cost: { status: "priced", usd: 0.0335, chf_reference: 0.02701775, known_usd: 0.0335, known_chf_reference: 0.02701775, unpriced_call_count: 0 },
    executions: [{
      id: "usage-1", role_label: "Textvorschlag", role_id: "A2_INNOSUISSE_PROPOSAL_WRITER", provider: "openai_direct", model: "gpt-5.6-luna", status: "succeeded",
      input_tokens: 20_000, cached_input_tokens: 5_000, cache_write_input_tokens: 0, output_tokens: 3_000, latency_ms: 900,
      cost: { status: "priced", usd: 0.0335, chf_reference: 0.02701775, known_usd: 0.0335, known_chf_reference: 0.02701775, unpriced_call_count: 0 },
      price_version: "2026-07-24.gpt56-luna",
    }],
  }],
}

describe("KostenScreen", () => {
  beforeEach(() => {
    mode = "live"
    activeProjectId = "project-1"
    mockedGetProjectCosts.mockClear()
    mockedGetProjectCosts.mockResolvedValue(exact)
  })

  it("zeigt nur echte USD-Daten und die klar markierte CHF-Orientierung", async () => {
    render(<KostenScreen />)

    expect(screen.getByRole("heading", { level: 1, name: "Kosten & Laufzeit" })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText("Exakte KI-Kosten")).toBeInTheDocument())
    expect(screen.getAllByText(/\$0\.0335/).length).toBeGreaterThan(0)
    expect(screen.getByText(/CHF-Orientierung: 1 USD = 0\.8065 CHF/)).toBeInTheDocument()
    expect(screen.getByText("Externe KI-Aufrufe aus 1 Durchlauf")).toBeInTheDocument()
    expect(screen.queryByText(/Beispieldaten|Projektlimit|Beispiel-Limit/)).toBeNull()
  })

  it("zeigt deutsche Status-Labels statt roher Backend-Keys und keinen Preis-Hinweis bei vollständiger Bepreisung", async () => {
    render(<KostenScreen />)

    expect(await screen.findByText("Abgeschlossen")).toBeInTheDocument()
    expect(screen.queryByText("completed")).toBeNull()
    expect(screen.queryByTestId("pricing-notice")).toBeNull()
  })

  it("zeigt Aufrufe nach Rolle gruppiert mit dem Modell darunter", async () => {
    render(<KostenScreen />)
    await screen.findByText("Durchlauf-Historie")
    fireEvent.click(screen.getByRole("button", { name: /Analyse-Durchlauf/ }))
    expect(screen.getByText("Innovationstext-Assistent")).toBeInTheDocument()
    expect(screen.getByText(/gpt-5\.6-luna · 1 Aufruf/)).toBeInTheDocument()
    expect(screen.queryByText(/openai_direct/)).toBeNull()
    expect(screen.getByText("Schutzlimit pro Lauf")).toBeInTheDocument()
  })

  it("kennzeichnet unvollständige Preise einmal zentral statt eine exakte Summe zu behaupten", async () => {
    mockedGetProjectCosts.mockResolvedValue({
      ...exact,
      runs: [{ ...exact.runs[0], cost: { status: "partial", known_usd: 0.01, known_chf_reference: 0.008, unpriced_call_count: 1 } }],
    })
    render(<KostenScreen />)
    const notice = await screen.findByTestId("pricing-notice")
    expect(notice).toHaveTextContent("Für 1 von 1 KI-Aufrufen lag zum Ausführungszeitpunkt noch keine veröffentlichte USD-Preisregel vor")
    expect(screen.getAllByTestId("pricing-notice")).toHaveLength(1)
    expect(screen.getByText(/Mindestens \$0\.0100/)).toBeInTheDocument()
    expect(screen.getByText("1 Aufruf unbepreist")).toBeInTheDocument()
    expect(screen.getByText("Unvollständig bepreist")).toBeInTheDocument()
    expect(screen.queryByText(/nicht vollständig bepreist/)).toBeNull()
  })

  it("zeigt laufende und gestoppte Durchläufe mit verständlichen Status-Labels", async () => {
    mockedGetProjectCosts.mockResolvedValue({
      ...exact,
      runs: [
        { ...exact.runs[0], id: "run-a", status: "running", ended_at: null },
        { ...exact.runs[0], id: "run-b", status: "stopped", stop_reason: "cost_budget_exhausted" },
      ],
    })
    render(<KostenScreen />)
    expect(await screen.findByText("Läuft")).toBeInTheDocument()
    expect(screen.getByText("Gestoppt: Kostenlimit")).toBeInTheDocument()
    expect(screen.queryByText("running")).toBeNull()
    expect(screen.queryByText("stopped")).toBeNull()
  })

  it("fasst interne Aufrufe ohne externe Kosten in einer Zeile zusammen", async () => {
    mockedGetProjectCosts.mockResolvedValue({
      ...exact,
      runs: [{
        ...exact.runs[0],
        llm_calls: 2,
        executions: [
          ...exact.runs[0].executions,
          {
            id: "usage-seed", role_label: "KI-Aufruf", provider: null, model: null, status: "recorded",
            input_tokens: 0, cached_input_tokens: 0, cache_write_input_tokens: 0, output_tokens: 0, latency_ms: null,
            cost: { status: "not_applicable", known_usd: 0, known_chf_reference: 0, unpriced_call_count: 0 },
            price_version: null,
          },
        ],
      }],
    })
    render(<KostenScreen />)
    fireEvent.click(await screen.findByRole("button", { name: /Analyse-Durchlauf/ }))
    expect(screen.getByText("1 interner Aufruf ohne externe KI-Kosten.")).toBeInTheDocument()
    expect(screen.queryByText("Unbekannter Dienst")).toBeNull()
    expect(screen.getByText("Externe KI-Aufrufe aus 1 Durchlauf")).toBeInTheDocument()
  })

  it("zeigt je Rolle einen Preis oder einen Strich mit einer gemeinsamen Fussnote", async () => {
    mockedGetProjectCosts.mockResolvedValue({
      ...exact,
      runs: [{
        ...exact.runs[0],
        llm_calls: 2,
        cost: { status: "partial", known_usd: 0.0335, known_chf_reference: 0.027, unpriced_call_count: 1 },
        executions: [
          ...exact.runs[0].executions,
          {
            id: "usage-2", role_label: "gpt-5.6-terra", role_id: "A3_INNOSUISSE_CRITICAL_REVIEWER", provider: "openai_direct", model: "gpt-5.6-terra", status: "succeeded",
            input_tokens: 500, cached_input_tokens: 0, cache_write_input_tokens: 0, output_tokens: 100, latency_ms: 800,
            cost: { status: "unknown_price", known_usd: 0, known_chf_reference: 0, unpriced_call_count: 1 },
            price_version: null,
          },
        ],
      }],
    })
    render(<KostenScreen />)
    fireEvent.click(await screen.findByRole("button", { name: /Analyse-Durchlauf/ }))
    expect(screen.getByText("Innovationstext-Assistent")).toBeInTheDocument()
    expect(screen.getByText("Qualitätskoordinator")).toBeInTheDocument()
    expect(screen.getAllByText(/\$0\.0335/).length).toBeGreaterThan(0)
    expect(screen.getByLabelText("Kein Preis bekannt")).toBeInTheDocument()
    expect(screen.getByText("Für 1 Aufruf lag zum Ausführungszeitpunkt noch keine Preisregel vor.")).toBeInTheDocument()
  })

  it("nennt Firecrawl-Web-Recherche ehrlich ohne USD-Preis und interne Werkzeuge korrekt", async () => {
    mockedGetProjectCosts.mockResolvedValue({
      ...exact,
      web_research_calls: 64,
      runs: [{ ...exact.runs[0], web_calls: 12 }],
    })
    render(<KostenScreen />)
    const note = await screen.findByTestId("firecrawl-note")
    expect(note).toHaveTextContent("Web-Recherche (Firecrawl): 64 Aufrufe — kreditbasiert, kein USD-Preis je Aufruf")
    fireEvent.click(screen.getByRole("button", { name: /Analyse-Durchlauf/ }))
    expect(screen.getByText("12 interne Werkzeug-Aufrufe (Quellen- und Feldabrufe); keine externen KI-Kosten.")).toBeInTheDocument()
  })

  it("zeigt keine Firecrawl-Zeile, wenn keine Web-Recherche stattfand", async () => {
    render(<KostenScreen />)
    await screen.findByText("Exakte KI-Kosten")
    expect(screen.queryByTestId("firecrawl-note")).toBeNull()
  })

  it("zeigt im Mock-Modus keine erfundenen Kosten", () => {
    mode = "mock"
    render(<KostenScreen />)
    expect(screen.getByText("Noch keine Live-Daten")).toBeInTheDocument()
    expect(mockedGetProjectCosts).not.toHaveBeenCalled()
  })
})
