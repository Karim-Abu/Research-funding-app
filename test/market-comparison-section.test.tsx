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
  it("deaktiviert «Vergleich erstellen» mit konkretem Grund ohne geprüfte Quelle", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(null)
      )
    )
    render(
      <MarketComparisonSection
        projectId={PROJECT}
        disabledReason="Noch keine live abgerufene, importierte und inhaltlich positiv geprüfte Quelle vorhanden."
      />
    )
    const button = await screen.findByRole("button", {
      name: "Vergleich erstellen",
    })
    expect(button).toBeDisabled()
    expect(
      screen.getByTestId("market-comparison-disabled-reason")
    ).toHaveTextContent(
      "Noch keine live abgerufene, importierte und inhaltlich positiv geprüfte Quelle vorhanden."
    )
  })

  // 2026-07-24 — Fortschritt (ohne «n von 2»-Ratio) + konkrete nächste Aktion.
  it("zeigt Fortschritt mit nächster Prüfaktion, wenn eine importierte Quelle ungeprüft ist", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(null)
      )
    )
    render(
      <MarketComparisonSection
        projectId={PROJECT}
        disabledReason="Noch keine live abgerufene, importierte und inhaltlich positiv geprüfte Quelle vorhanden."
        readiness={{
          hasEligible: false,
          eligibleCount: 0,
          totalImported: 1,
          nextCandidate: {
            result_id: "res-1",
            title: "Switzerland Cybersecurity Report",
            missingStep: "review",
          },
        }}
      />
    )
    expect(
      await screen.findByTestId("market-comparison-readiness")
    ).toHaveTextContent(
      "Noch keine geeigneten Quellen — als Nächstes: «Switzerland Cybersecurity Report» inhaltlich prüfen (Stützt/Teilweise)."
    )
  })

  it("zeigt die Import-Variante und ab 1 geeigneten Quelle die Kann-erstellt-werden-Zeile", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(null)
      )
    )
    const { rerender } = render(
      <MarketComparisonSection
        projectId={PROJECT}
        readiness={{
          hasEligible: false,
          eligibleCount: 0,
          totalImported: 1,
          nextCandidate: { result_id: "res-2", title: "Marktreport", missingStep: "import" },
        }}
      />
    )
    expect(
      await screen.findByTestId("market-comparison-readiness")
    ).toHaveTextContent("«Marktreport» übernehmen und prüfen.")
    rerender(
      <MarketComparisonSection
        projectId={PROJECT}
        readiness={{
          hasEligible: true,
          eligibleCount: 1,
          totalImported: 2,
          nextCandidate: null,
        }}
      />
    )
    expect(
      screen.getByTestId("market-comparison-readiness")
    ).toHaveTextContent(
      "1 geeignete Quelle ausgewählt — mindestens 2 empfohlen für einen belastbaren Vergleich."
    )
  })

  it("blendet die Fortschrittszeile ohne importierte Quellen aus und erklärt den Mehrwert", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(null)
      )
    )
    render(
      <MarketComparisonSection
        projectId={PROJECT}
        readiness={{ hasEligible: false, eligibleCount: 0, totalImported: 0, nextCandidate: null }}
      />
    )
    await screen.findByText(/Noch kein Vergleich/)
    expect(screen.queryByTestId("market-comparison-readiness")).toBeNull()
    expect(
      screen.getByText(/Das liefert der Vergleich: eine belegte Tabelle/)
    ).toBeInTheDocument()
  })

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
    expect(screen.getByText(/live ab, importieren und prüfen/)).toBeInTheDocument()
  })

  it("shows the precise reviewed-live empty result", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(comparison({
          items: [],
          item_count: 0,
          research_gaps: [
            "Keine live abgerufenen und inhaltlich positiv geprüften öffentlichen Quellen mit marktbezogenen Passagen vorhanden.",
          ],
        }))
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    expect(await screen.findByText(
      /Keine Vergleichseinträge aus live abgerufenen und inhaltlich positiv/
    )).toBeInTheDocument()
    expect(screen.getByTestId("market-research-gaps")).toHaveTextContent(
      "Keine live abgerufenen und inhaltlich positiv geprüften öffentlichen Quellen"
    )
  })

  it("RUN 4A: kompakte Spalten und höchstens fünf Konsequenzen", async () => {
    const consequences = [
      "Konsequenz 1",
      "Konsequenz 2",
      "Konsequenz 3",
      "Konsequenz 4",
      "Konsequenz 5",
      "Konsequenz 6 (darf nicht erscheinen)",
    ]
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(
          comparison({
            consequences,
            items: [
              {
                ...comparison().items[0],
                target_customer_segment: "Schweizer KMU",
                core_problem_or_benefit: "Schnellere Qualitätsprüfung",
                price_business_model: "Abo-Modell",
                swiss_relevance: "Standort Zürich erwähnt",
              },
            ],
          })
        )
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    await waitFor(() =>
      expect(screen.getByTestId("market-comparison-table")).toBeInTheDocument()
    )
    // Mandats-Spalten der kompakten Tabelle.
    for (const column of [
      "Anbieter/Alternative",
      "Zielgruppe",
      "Kernnutzen",
      "Differenzierung",
      "Geschäftsmodell",
      "Schweiz-Relevanz",
      "Belege",
    ]) {
      expect(screen.getByText(column)).toBeInTheDocument()
    }
    expect(screen.getByText("Schweizer KMU")).toBeInTheDocument()
    expect(screen.getByText("Schnellere Qualitätsprüfung")).toBeInTheDocument()
    expect(screen.getByText("Abo-Modell")).toBeInTheDocument()
    // Ehrlicher Gesamtstatus im Sektionskopf (einheitliches Viewmodel).
    expect(screen.getByTestId("market-comparison-status")).toHaveTextContent(
      "Zur Prüfung bereit"
    )
    // Höchstens fünf Konsequenzen.
    const list = screen.getByTestId("market-consequences")
    expect(list).toHaveTextContent("Was das für den Antrag bedeutet")
    expect(list).toHaveTextContent("Konsequenz 5")
    expect(list).not.toHaveTextContent("Konsequenz 6")
  })

  it("RUN 4A: limited mit item_count 0 erscheint nie als Erfolg", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(
          comparison({
            status: "limited",
            items: [],
            item_count: 0,
            research_gaps: ["Es fehlen geprüfte Quellen zu Anbietern im Zielmarkt."],
          })
        )
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    expect(
      await screen.findByText(/keine belastbaren Anbieter- oder/)
    ).toBeInTheDocument()
    // Kein Erfolgs-Empty-State, keine leere Tabelle.
    expect(
      screen.queryByText(/Keine Vergleichseinträge aus live abgerufenen/)
    ).toBeNull()
    expect(screen.queryByTestId("market-comparison-table")).toBeNull()
    // Limitationshinweis + fehlende Evidenz konkret benannt.
    expect(
      screen.getByText(/Begrenzte externe Evidenz: Es liegen geprüfte Marktquellen vor/)
    ).toBeInTheDocument()
    expect(screen.getByTestId("market-research-gaps")).toHaveTextContent(
      "Es fehlen geprüfte Quellen zu Anbietern im Zielmarkt."
    )
  })

  it("RUN 4A: insufficient nennt fehlende geeignete geprüfte Quellen", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(
          comparison({
            status: "insufficient_external_evidence",
            items: [],
            item_count: 0,
          })
        )
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    expect(
      await screen.findByText(
        /Für einen belastbaren Marktvergleich fehlen geeignete geprüfte/
      )
    ).toBeInTheDocument()
    expect(screen.getByTestId("market-comparison-status")).toHaveTextContent(
      "Zu wenige geprüfte Quellen"
    )
  })

  it("zeigt das Gesamturteil-Board über dem Detail, wenn das Backend es liefert", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(
          comparison({
            competition_judgment: {
              status: "similar_solutions_found",
              rationale: "Im definierten Suchumfang existieren ähnliche Lösungen.",
              scope_summary: "Im definierten Suchumfang: 2 geprüfte öffentliche Quellen, 1 untersuchte Lösungskandidaten.",
              relevant_candidate_count: 1,
              key_overlaps: [],
              evidenced_differentiators: [],
              plausible_unverified_differentiators: [],
              open_evidence_gaps: [],
              allowed_formulations: [],
              disallowed_formulations: ["weltweit einzigartig"],
              can_insert_into_application: false,
            },
          })
        )
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    const board = await screen.findByTestId("market-section-judgment")
    expect(board).toHaveTextContent("Ähnliche Lösungen gefunden")
    expect(board).toHaveTextContent("Im definierten Suchumfang")
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
