import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
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

// Die Lösungslandschaft-Tabelle, Marktbild-Prüfliste, Konsequenzen und
// Quellenliste liegen hinter «Details öffnen» (Ergebnis-zuerst-Ansicht).
async function openDetails() {
  fireEvent.click(await screen.findByRole("button", { name: "Details öffnen" }))
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
      "Noch keine geeigneten Quellen — als Nächstes: «Switzerland Cybersecurity Report» ausdrücklich freigeben (nicht vertrauenswürdiges Inhaltssignal)."
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
      "1 geeignete Quelle ausgewählt — mindestens 2 empfohlen, damit der Vergleich mehr als einen Blickwinkel abdeckt."
    )
  })

  // Zwei Quellen machen den Vergleich möglich, aber nicht belastbar — die UI
  // darf das nicht versprechen.
  it("verspricht bei zwei Quellen keine Belastbarkeit", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(null)
      )
    )
    render(
      <MarketComparisonSection
        projectId={PROJECT}
        readiness={{ hasEligible: true, eligibleCount: 2, totalImported: 2, nextCandidate: null }}
      />
    )
    const line = await screen.findByTestId("market-comparison-readiness")
    expect(line).toHaveTextContent("der Vergleich kann erstellt werden")
    expect(line).toHaveTextContent("bleibt auf die geprüften Quellen beschränkt")
    expect(line.textContent).not.toMatch(/belastbar/i)
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
    await screen.findByText(/Es liegt noch kein Markt- und Konkurrenzvergleich vor/)
    expect(screen.queryByTestId("market-comparison-readiness")).toBeNull()
    expect(screen.getByTestId("market-section-next-step")).toHaveTextContent(
      "Öffentliche Quellen recherchieren, übernehmen und inhaltlich prüfen"
    )
  })

  it("renders the comparison table, quote, status label and research gaps", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(comparison())
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    await openDetails()
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

  // Kernregel: Marktstatistiken sind keine Wettbewerber. Sie erscheinen in der
  // Marktbild-Prüfliste, niemals als Zeile der Anbieter-/Alternativen-Tabelle.
  it("trennt Marktaussagen von der Lösungstabelle und listet die verwendeten Quellen", async () => {
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
    await openDetails()
    const table = await screen.findByTestId("market-comparison-table")
    // Lösungen: nach Lösungsart gruppiert, keine Kategorie-Sammeltitel mehr.
    expect(table).toHaveTextContent("Lösungslandschaft")
    expect(table).toHaveTextContent("Angrenzende Lösung (1)")
    expect(table).toHaveTextContent("Acme Plattform")
    // Marktaussagen stehen NICHT in der Vergleichstabelle.
    expect(table).not.toHaveTextContent("Marktwachstum Bericht")
    expect(table).not.toHaveTextContent("Manuelle Prüfung dauert lange")
    expect(screen.queryByText("Marktgrössen-Kandidaten")).toBeNull()
    expect(screen.queryByText("Wettbewerber und Alternativen")).toBeNull()
    // …sondern in der Prüfliste des Marktbilds.
    const claims = screen.getByTestId("market-claims-review")
    expect(claims).toHaveTextContent("Marktaussagen prüfen (2)")
    expect(claims).toHaveTextContent("Marktwachstum Bericht")
    expect(claims).toHaveTextContent("Manuelle Prüfung dauert lange")
    const used = screen.getByTestId("market-used-sources")
    expect(used).toHaveTextContent("Verwendete Quellen")
    expect(used).toHaveTextContent("Marktbericht (öffentlich)")
    expect(used).toHaveTextContent("Branchenstudie")
    // Nie rohe IDs in der Standard-UI.
    expect(used).not.toHaveTextContent("s1")
  })

  // Die Trennung darf die menschliche Prüfung nicht wegnehmen (HITL).
  it("lässt Marktaussagen weiterhin fachlich prüfen", async () => {
    const claim = {
      ...comparison().items[0],
      item_id: "i2",
      name: "Marktwachstum Bericht",
      category: "market_size_claim",
    }
    let patched: { itemId?: string; body?: unknown } = {}
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(comparison({ items: [claim], item_count: 1 }))
      ),
      http.post(
        "/api/market-comparison-items/:itemId/status",
        async ({ params, request }) => {
          patched = { itemId: params.itemId as string, body: await request.json() }
          return HttpResponse.json({ ok: true })
        }
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    await openDetails()
    const supports = await screen.findByRole("button", {
      name: "Marktwachstum Bericht: Stützt",
    })
    fireEvent.click(supports)
    await waitFor(() => expect(patched.itemId).toBe("i2"))
    expect(patched.body).toMatchObject({ support_status: "supports" })
  })

  it("erklärt, warum ein Vergleich veraltet ist", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(comparison({ scope_stale: true, stale_reason: "scope_changed" }))
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    // Veraltung ist ein Zustand, kein Zusatzhinweis: sie bestimmt Badge,
    // Antwort und nächsten Schritt.
    expect(await screen.findByTestId("market-comparison-status")).toHaveTextContent(
      "Veraltet — neu erstellen"
    )
    expect(screen.getByTestId("market-section-judgment")).toHaveTextContent("Suchraum")
    expect(screen.getByTestId("market-section-next-step")).toHaveTextContent(
      "Vergleich neu erstellen"
    )
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
    await openDetails()
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
      expect(
        screen.getByText(/Es liegt noch kein Markt- und Konkurrenzvergleich vor/)
      ).toBeInTheDocument()
    )
    expect(
      screen.getByRole("button", { name: "Vergleich erstellen" })
    ).toBeInTheDocument()
    expect(screen.getByTestId("market-section-next-step")).toHaveTextContent(
      "danach den Vergleich erstellen"
    )
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
    // Ohne belegte Lösungskandidaten ist das Ergebnis kein leerer Erfolg.
    expect(await screen.findByTestId("market-comparison-status")).toHaveTextContent(
      "Weitere Recherche nötig"
    )
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
    await openDetails()
    let table: HTMLElement
    await waitFor(() => {
      table = screen.getByTestId("market-comparison-table")
      expect(table).toBeInTheDocument()
    })
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
    // Scoped auf die Tabelle: «Was bereits bekannt ist» zeigt dieselben
    // belegten Werte (z. B. Kundengruppe) ausserhalb der Tabelle nochmals.
    expect(within(table!).getByText("Schweizer KMU")).toBeInTheDocument()
    expect(within(table!).getByText("Schnellere Qualitätsprüfung")).toBeInTheDocument()
    expect(within(table!).getByText("Abo-Modell")).toBeInTheDocument()
    // Ein Eintrag ohne Lösungslandschaft trägt noch keine Wettbewerbsaussage.
    expect(screen.getByTestId("market-comparison-status")).toHaveTextContent(
      "Weitere Recherche nötig"
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
    // Kein Erfolgs-Empty-State: ein Status, der zur Recherche auffordert.
    expect(await screen.findByTestId("market-comparison-status")).toHaveTextContent(
      "Weitere Recherche nötig"
    )
    expect(screen.queryByTestId("market-comparison-table")).toBeNull()
    // Der nächste Schritt benennt die fehlende Wettbewerbsabdeckung.
    expect(screen.getByTestId("market-section-next-step")).toHaveTextContent(
      "decken den Wettbewerb noch nicht ab"
    )
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
    expect(await screen.findByTestId("market-comparison-status")).toHaveTextContent(
      "Weitere Recherche nötig"
    )
    expect(screen.getByTestId("market-section-next-step")).toHaveTextContent(
      "zu wenige geeignete geprüfte öffentliche Quellen"
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
    // Die Begründung des Backends ist die Antwort — kein zusätzlicher Statuschip.
    expect(board).toHaveTextContent("Im definierten Suchumfang existieren ähnliche Lösungen.")
    expect(board).toHaveTextContent("2 geprüfte öffentliche Quellen")
  })

  // Reale Lage aus der Abnahme: mehrere Quellen geprüft und übernommen, aber
  // alle nur mit Marktzahlen — 0 Lösungskandidaten. Der Grund darf dann nicht
  // «noch nicht bestätigt» behaupten, sondern muss die fehlende Lösungsquelle
  // benennen.
  it("nennt bei geprüften Quellen ohne Lösungskandidaten den Marktinfo-Grund", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(
          comparison({
            // Genug Quellen — was fehlt, sind Lösungskandidaten.
            source_version_ids: ["v1", "v2", "v3"],
            solution_landscape: { candidates: [], candidate_count_by_type: {} },
            competition_judgment: {
              status: "insufficient_evidence",
              rationale: "Die geprüfte Quellenlage reicht für eine belastbare Wettbewerbsaussage noch nicht aus.",
              scope_summary: "Im definierten Suchumfang: 3 geprüfte öffentliche Quellen, 0 untersuchte Lösungskandidaten.",
              relevant_candidate_count: 0,
              key_overlaps: [],
              evidenced_differentiators: [],
              plausible_unverified_differentiators: [],
              open_evidence_gaps: [],
              allowed_formulations: [],
              disallowed_formulations: [],
              can_insert_into_application: false,
            },
          })
        )
      )
    )
    render(<MarketComparisonSection projectId={PROJECT} />)
    const nextStep = await screen.findByTestId("market-section-next-step")
    expect(nextStep).toHaveTextContent("kein konkreter Anbieter und keine Alternativlösung")
    expect(nextStep.textContent).not.toMatch(/inhaltlich bestätigt/)
  })

  // Widerspruch aus der Abnahme: oben «Quellenlage reicht nicht aus», darunter
  // «der Vergleich kann erstellt werden». Die Fortschrittszeile gilt nur, so
  // lange noch kein Vergleich existiert.
  it("zeigt die Fortschrittszeile nicht mehr, sobald ein Vergleich vorliegt", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(comparison({ source_version_ids: ["v1", "v2", "v3"] }))
      )
    )
    render(
      <MarketComparisonSection
        projectId={PROJECT}
        readiness={{ hasEligible: true, eligibleCount: 11, totalImported: 11, nextCandidate: null }}
      />
    )
    await screen.findByTestId("market-comparison-status")
    expect(screen.queryByTestId("market-comparison-readiness")).toBeNull()
    expect(screen.queryByText(/der Vergleich kann erstellt werden/)).toBeNull()
  })

  it("benennt stattdessen die noch nicht einbezogenen Quellen", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(comparison({ source_version_ids: ["v1", "v2", "v3"] }))
      )
    )
    render(
      <MarketComparisonSection
        projectId={PROJECT}
        readiness={{ hasEligible: true, eligibleCount: 11, totalImported: 11, nextCandidate: null }}
      />
    )
    expect(await screen.findByTestId("market-comparison-status")).toHaveTextContent(
      "Veraltet — neu erstellen"
    )
    expect(screen.getByTestId("market-section-judgment")).toHaveTextContent(
      "8 geprüfte Quellen dazugekommen"
    )
  })

  it("meldet keine neuen Quellen, wenn der Vergleich alle geprüften nutzt", async () => {
    server.use(
      http.get(`/api/projects/${PROJECT}/market-comparisons/latest`, () =>
        HttpResponse.json(comparison({ source_version_ids: ["v1", "v2"] }))
      )
    )
    render(
      <MarketComparisonSection
        projectId={PROJECT}
        readiness={{ hasEligible: true, eligibleCount: 2, totalImported: 2, nextCandidate: null }}
      />
    )
    expect(await screen.findByTestId("market-comparison-status")).not.toHaveTextContent(
      "Veraltet"
    )
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
    await openDetails()
    await waitFor(() =>
      expect(screen.getByTestId("market-comparison-table")).toBeInTheDocument()
    )
    expect(screen.getByText("Acme Plattform")).toBeInTheDocument()
  })
})
