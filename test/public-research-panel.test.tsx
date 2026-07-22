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
  research_goal: "KI-gestützte Datenanalyse für Schweizer KMU – Zürich/DACH (B2B)",
  search_tags: ["Datenanalyse", "KMU"],
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

  it("shows the four active modules in a suggested draft", async () => {
    let workspace = emptyWorkspace()
    const draft = {
      ...brief,
      status: "draft" as const,
      approved_at: null,
      research_goal: "",
      search_tags: [],
      application_domain: "",
      technology_class: "",
      target_customer_segments: [],
      competence_needs: [],
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
    // Anf. 8 — die fachliche Leitfrage statt eines technischen Formulars.
    expect(
      screen.getByRole("heading", { name: "Was soll öffentlich recherchiert werden?" })
    ).toBeInTheDocument()
    for (const label of [
      "Markt & Wachstum", "Wettbewerb & Alternativen",
      "State of the Art", "Mögliche Schweizer Forschungspartner",
    ]) expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.getByText(
      "Beispiel: KI-gestützte Datenanalyse für Schweizer KMU – Zürich/DACH (B2B)"
    )).toBeInTheDocument()
    expect(screen.getByText("Beispiel: Schweiz / DACH")).toBeInTheDocument()
    expect(screen.getByText(/Vorschläge bestätigen keine fachliche Richtigkeit/)).toBeInTheDocument()
    expect(screen.getByText(/interne Projekt- oder Partnerdaten gehören nicht hierher/)).toBeInTheDocument()
  })

  it("validates the simplified public research goal only when it is saved or approved", async () => {
    const invalidDraft = {
      ...brief,
      status: "draft" as const,
      approved_at: null,
      research_goal: "",
      search_tags: [],
      application_domain: "Medizintechnik",
      technology_class: "Medizin-Technik",
      target_customer_segments: ["Schweizer KMU"],
      competence_needs: ["FHNW"],
    }
    let saveCalls = 0
    server.use(
      http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json({
        ...emptyWorkspace(),
        brief: { latest: invalidDraft, active_approved: null },
      })),
      http.put(`/api/projects/${PROJECT}/research-brief`, () => {
        saveCalls += 1
        return HttpResponse.json(invalidDraft)
      }),
    )
    render(<PublicResearchPanel projectId={PROJECT} />)
    fireEvent.click(await screen.findByRole("button", { name: "Public-safe Brief freigeben" }))
    expect(await screen.findByText(
      "Bitte eine öffentliche Recherchefrage oder ein Ziel angeben."
    )).toBeInTheDocument()
    expect(saveCalls).toBe(0)
  })

  it("accepts paste and Unicode punctuation without key filtering, then normalizes only at save", async () => {
    const draft = { ...brief, status: "draft" as const, approved_at: null, research_goal: "", search_tags: [] }
    let savedBody: Record<string, unknown> | null = null
    server.use(
      http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json({ ...emptyWorkspace(), brief: { latest: draft, active_approved: null } })),
      http.put(`/api/projects/${PROJECT}/research-brief`, async ({ request }) => {
        savedBody = await request.json() as Record<string, unknown>
        return HttpResponse.json({ ...draft, ...savedBody })
      }),
    )
    render(<PublicResearchPanel projectId={PROJECT} />)
    const goal = await screen.findByLabelText("Recherchefrage / Ziel")
    fireEvent.change(goal, { target: { value: "  KI-gestützte Datenanalyse für Schweizer KMU – Zürich/DACH (B2B)  " } })
    fireEvent.click(screen.getByRole("button", { name: "Entwurf speichern" }))
    await waitFor(() => expect(savedBody).not.toBeNull())
    expect(savedBody?.research_goal).toBe("KI-gestützte Datenanalyse für Schweizer KMU – Zürich/DACH (B2B)")
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
    expect(screen.getByText("Kandidat")).toBeInTheDocument()
    // Anf. 9 — die drei primären Entscheidungen pro Resultat.
    expect(screen.getByRole("button", { name: /Öffnen/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Verwerfen" })).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Übernehmen und prüfen" }))
    expect(await screen.findByText("Übernommen")).toBeInTheDocument()
    expect(screen.getByText("Fundstelle aus abgerufener Seite")).toBeInTheDocument()
    // Nach dem Import: die drei Prüf-Entscheidungen.
    expect(screen.getByRole("button", { name: "Stützt" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Teilweise" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Stützt nicht" })).toBeInTheDocument()
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
    expect(screen.queryByRole("button", { name: /Übernehmen/ })).toBeNull()
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
    const edit = await screen.findByRole("button", { name: "Brief ändern" })
    expect(screen.queryByLabelText("Recherchefrage / Ziel")).toBeNull()
    fireEvent.click(edit)
    expect(await screen.findByLabelText("Recherchefrage / Ziel")).toBeEnabled()
    expect(screen.getByRole("button", { name: "Neue Briefversion speichern" })).toBeEnabled()
  })

  it("RUN 4A: zeigt nie Roh-Enums oder Roh-Risikoscores im Standardfluss", async () => {
    const workspace = liveWorkspace()
    workspace.queries[0].risk_score = 3
    workspace.results[0] = {
      ...workspace.results[0],
      source_quality: "institutionell_ungeprüft",
      coverage_status: "exact_quote_verified",
    }
    server.use(http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(workspace)))
    render(<PublicResearchPanel projectId={PROJECT} />)
    expect(await screen.findByText("Institutionell (ungeprüft)")).toBeInTheDocument()
    expect(screen.getByText("Textstelle exakt gefunden")).toBeInTheDocument()
    // Roh-Werte und Score-Bruchzahlen erscheinen nirgends.
    expect(screen.queryByText(/institutionell_ungeprüft/)).toBeNull()
    expect(screen.queryByText(/exact_quote_verified/)).toBeNull()
    expect(screen.queryByText(/\(\d+\/10\)/)).toBeNull()
    // Die verständliche Risikostufe bleibt sichtbar.
    expect(screen.getByText(/Risiko niedrig/)).toBeInTheDocument()
  })

  it("RUN 4A: nicht erreichbarer Recherchedienst — ehrlicher Hinweis und manueller Import ohne Brief", async () => {
    server.use(http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(emptyWorkspace())))
    render(<PublicResearchPanel projectId={PROJECT} />)
    const banner = await screen.findByTestId("research-unavailable-banner")
    expect(banner).toHaveTextContent(
      "Die öffentliche Recherche ist momentan nicht erreichbar."
    )
    expect(banner).toHaveTextContent("Ihre Daten wurden nicht verändert")
    // Kein Rohstatus im Fluss; Badge in Nutzersprache.
    expect(screen.queryByText("unavailable")).toBeNull()
    expect(screen.getByText("Vorübergehend nicht verfügbar")).toBeInTheDocument()
    // Der manuelle Import hängt nicht am freigegebenen Brief.
    expect(screen.getByTestId("manual-research-fallback")).toBeInTheDocument()
  })

  it("RUN 4A: genau eine Modul-Darstellung — offenes Brief-Formular blendet den Ergebnisbereich aus", async () => {
    const workspace = liveWorkspace()
    workspace.brief = {
      latest: { ...brief, research_brief_id: "brief-2", version: 2, status: "draft", approved_at: null },
      active_approved: brief,
    }
    server.use(http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(workspace)))
    render(<PublicResearchPanel projectId={PROJECT} />)
    expect(await screen.findByTestId("research-brief-form")).toBeInTheDocument()
    // Modul-Checkboxen sind sichtbar, der Ergebnis-Umschalter nicht.
    expect(screen.getByText("Recherchemodule")).toBeInTheDocument()
    expect(screen.queryByText("Ergebnisse nach Modul")).toBeNull()
    expect(screen.queryByText("Swiss market report")).toBeNull()
  })

  it("labels partner results as candidates without eligibility claims", async () => {
    server.use(http.get(`/api/projects/${PROJECT}/research-workspace`, () => HttpResponse.json(liveWorkspace("swiss_research_partners"))))
    render(<PublicResearchPanel projectId={PROJECT} />)
    fireEvent.click(await screen.findByRole("button", { name: "Mögliche Schweizer Forschungspartner" }))
    expect((await screen.findAllByText("Applied Research Lab")).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText(/Kein belastbarer Nachweis – menschlich prüfen/)).toBeInTheDocument()
    expect(screen.getByText("Standort").nextSibling).toHaveTextContent("unbestätigt")
    expect(screen.getByText(/anomaly detection, applied machine learning/)).toBeInTheDocument()
  })
})
