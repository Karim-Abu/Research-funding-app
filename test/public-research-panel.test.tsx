import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { PublicResearchPanel } from "@/components/quellen/public-research-panel"
import type { ResearchWorkspaceDto } from "@/lib/research-brief"

const PROJECT = "p1"
const NOW = "2026-07-14T08:00:00Z"

const brief = {
  research_brief_id: "brief-1",
  version: 1,
  status: "approved" as const,
  application_domain: "industrial quality",
  technology_class: "anomaly detection",
  target_customer_segments: ["manufacturing SMEs"],
  region: "Switzerland",
  competence_needs: ["applied machine learning"],
  modules: ["market_growth", "swiss_research_partners"] as const,
  approved_at: NOW,
}

function emptyWorkspace(): ResearchWorkspaceDto {
  return {
    brief: { latest: null, active_approved: null },
    queries: [],
    results: [],
    provider_mode: "unavailable",
  }
}

function liveWorkspace(module: "market_growth" | "swiss_research_partners" = "market_growth"): ResearchWorkspaceDto {
  return {
    brief: { latest: brief, active_approved: brief },
    provider_mode: "live",
    queries: [{
      approval_id: "approval-1",
      research_brief_id: brief.research_brief_id,
      module,
      planner_purpose: module === "market_growth" ? "market_size" : "org_competence",
      query_text: "industrial quality anomaly detection Switzerland",
      firewall_decision: "require_human_approval",
      risk_label: "low",
      redaction_summary: [],
      status: "approved",
      task_id: "task-1",
      task_status: "succeeded",
      execution_mode: "live",
    }],
    results: [{
      result_id: "result-1",
      task_id: "task-1",
      module,
      planner_purpose: module === "market_growth" ? "market_size" : "org_competence",
      title: module === "market_growth" ? "Swiss market report" : "Applied Research Lab",
      source_url: "https://research.example.edu/report",
      final_url: "https://research.example.edu/report",
      domain: "research.example.edu",
      snippet: "A concrete public result excerpt.",
      retrieved_at: NOW,
      relevance_reason: "Treffer zum freigegebenen Recherchemodul; fachlich prüfen.",
      status: "candidate",
      execution_mode: "live",
      source_document_id: null,
      source_locations: [],
      partner_candidate: module === "swiss_research_partners" ? {
        organization_or_group: "Applied Research Lab",
        location: null,
        location_status: "unverified",
        expertise_keywords: ["anomaly detection", "applied machine learning"],
        possible_project_role: "Mögliche fachliche Passung als Forschungspartner (nicht geprüft).",
        why_potentially_relevant: "Treffer zur freigegebenen Kompetenzsuche.",
        evidence_url: "https://research.example.edu/report",
        status: "candidate_not_eligibility_confirmed",
      } : null,
    }],
  }
}

describe("PublicResearchPanel", () => {
  it("starts with the public-safe brief workflow and no free query", async () => {
    server.use(http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(emptyWorkspace())))
    render(<PublicResearchPanel projectId={PROJECT} />)
    expect(await screen.findByRole("button", { name: /Recherchebrief vorschlagen/ })).toBeInTheDocument()
    expect(screen.getByText(/Queries entstehen nur aus dem geprüften öffentlichen Recherchebrief/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/Öffentlicher Suchbegriff/)).toBeNull()
    expect(screen.queryByText(/firecrawl|api[_ ]?key|token/i)).toBeNull()
  })

  it("blocks NDA data without any research action", () => {
    render(<PublicResearchPanel projectId={PROJECT} dataClass="nda" />)
    expect(screen.getByText(/NDA-geschützte oder unklare Datenklassen/)).toBeInTheDocument()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("shows all five modules in a suggested draft", async () => {
    let workspace = emptyWorkspace()
    const draft = {
      ...brief,
      status: "draft" as const,
      approved_at: null,
      modules: [
        "market_growth", "competition_alternatives", "customer_problem",
        "state_of_the_art", "swiss_research_partners",
      ] as const,
    }
    server.use(
      http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(workspace)),
      http.post(`/api/projects/${PROJECT}/research-brief/suggest`, () => {
        workspace = { ...workspace, brief: { latest: draft, active_approved: null } }
        return HttpResponse.json(draft)
      }),
    )
    render(<PublicResearchPanel projectId={PROJECT} />)
    fireEvent.click(await screen.findByRole("button", { name: /Recherchebrief vorschlagen/ }))
    expect(await screen.findByTestId("research-brief-form")).toBeInTheDocument()
    for (const label of [
      "Markt & Wachstum", "Wettbewerb & Alternativen", "Kundenproblem & Bedarf",
      "State of the Art", "Mögliche Schweizer Forschungspartner",
    ]) expect(screen.getByText(label)).toBeInTheDocument()
  })

  it("shows live URL, module relevance and imports through the existing source path", async () => {
    let workspace = liveWorkspace()
    server.use(
      http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(workspace)),
      http.post("/api/research-results/result-1/import", () => {
        workspace = {
          ...workspace,
          results: workspace.results.map((row) => ({
            ...row,
            status: "imported" as const,
            source_document_id: "source-1",
            source_locations: [{
              source_id: "source-1", source_version_id: "version-1",
              page: null, section: "Market", excerpt: "Fetched exact page location.",
            }],
          })),
        }
        return HttpResponse.json({ source_id: "source-1", status: "processed" }, { status: 201 })
      }),
    )
    render(<PublicResearchPanel projectId={PROJECT} />)
    expect(await screen.findByText("Swiss market report")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "https://research.example.edu/report" })).toHaveAttribute(
      "href", "https://research.example.edu/report",
    )
    expect(screen.getByText(/Quellenkandidat – fachlich prüfen/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Übernehmen" }))
    expect(await screen.findByText("Übernommen")).toBeInTheDocument()
    expect(screen.getByText("Fundstelle aus abgerufener Seite")).toBeInTheDocument()
  })

  it("marks demo results honestly and never offers import", async () => {
    const workspace = liveWorkspace()
    workspace.provider_mode = "fake_demo"
    workspace.queries[0].execution_mode = "fake_demo"
    workspace.results[0] = {
      ...workspace.results[0], execution_mode: "fake_demo",
      source_url: "https://example.org/demo", final_url: null, domain: "example.org",
    }
    server.use(http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(workspace)))
    render(<PublicResearchPanel projectId={PROJECT} />)
    expect(await screen.findByTestId("research-demo-banner")).toHaveTextContent(
      "Demo-Recherche – keine echten Webquellen",
    )
    expect(screen.getByText("Demo")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Übernehmen" })).toBeNull()
  })

  it("keeps historical query status without blocking a new approved brief", async () => {
    const workspace = liveWorkspace()
    const nextBrief = {
      ...brief,
      research_brief_id: "brief-2",
      version: 2,
    }
    workspace.brief = { latest: nextBrief, active_approved: nextBrief }
    workspace.queries[0].status = "expired"
    server.use(http.get(
      `/api/projects/${PROJECT}/research-workspace`,
      () => HttpResponse.json(workspace),
    ))
    render(<PublicResearchPanel projectId={PROJECT} />)
    expect(await screen.findByRole("button", { name: "Queries erzeugen" })).toBeEnabled()
    expect(screen.getByText("Frühere Query-Stände")).toBeInTheDocument()
    expect(screen.getByText("Abgelaufen")).toBeInTheDocument()
  })

  it("opens an approved brief explicitly for a new version", async () => {
    server.use(http.get(
      `/api/projects/${PROJECT}/research-workspace`,
      () => HttpResponse.json(liveWorkspace()),
    ))
    render(<PublicResearchPanel projectId={PROJECT} />)
    const domain = await screen.findByLabelText("Anwendungsdomäne")
    expect(domain).toBeDisabled()
    fireEvent.click(screen.getByRole("button", { name: "Brief ändern" }))
    expect(domain).toBeEnabled()
    expect(screen.getByRole("button", { name: "Neue Briefversion speichern" })).toBeEnabled()
  })

  it("labels partner results as candidates without eligibility claims", async () => {
    server.use(http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(liveWorkspace("swiss_research_partners"))))
    render(<PublicResearchPanel projectId={PROJECT} />)
    fireEvent.click(await screen.findByRole("button", { name: "Mögliche Schweizer Forschungspartner" }))
    expect((await screen.findAllByText("Applied Research Lab")).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText(/Kandidat – keine Förderberechtigung bestätigt/)).toBeInTheDocument()
    expect(screen.getByText("Standort").nextSibling).toHaveTextContent("unbestätigt")
    expect(screen.getByText(/anomaly detection, applied machine learning/)).toBeInTheDocument()
  })
})
