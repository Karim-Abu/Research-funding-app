// Detail-Sheet: Gesamturteil, strikte Trennung Marktbild vs. Lösungslandschaft,
// nur zulässige Aussagen einfügbar, unzulässige als Sperr-Block, keine verbotenen
// Phrasen und keine Prozentwerte.
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import { MarketComparisonSheet } from "@/components/editor/market-comparison-sheet"
import type {
  CompetitionJudgmentDto,
  MarketComparisonDto,
  SolutionLandscapeCandidateDto,
} from "@/lib/market-comparison"

const FORBIDDEN = [
  "weltweit einzigartig",
  "keine Konkurrenz",
  "Es existiert keine solche Lösung",
  "patentierbar",
]

function candidate(over: Partial<SolutionLandscapeCandidateDto> = {}): SolutionLandscapeCandidateDto {
  return {
    item_id: "cand-1",
    name: "Rival AG",
    candidate_type: "direct_competitor",
    relation_to_project: "competing",
    relevant_functions: ["Erkennung", "Meldung"],
    overlaps: ["Erkennung", "Meldung"],
    evidencing_differentiators: [],
    unverified_differentiators: ["Zentralere Architektur (zu prüfen)."],
    source_document_ids: ["s1"],
    evidence_quotes: [{ quote: "Rival bietet Erkennung.", source_document_id: "s1", source_version_id: "v1" }],
    status: "proposed",
    confidence_label: "source_backed",
    support_status: "unreviewed",
    source_scope_ok: true,
    allowed_formulations: ["Im definierten Suchumfang wurde mit Rival AG eine vergleichbare Lösung identifiziert."],
    disallowed_formulations: FORBIDDEN,
    ...over,
  }
}

function judgment(over: Partial<CompetitionJudgmentDto> = {}): CompetitionJudgmentDto {
  return {
    status: "direct_equivalent_found",
    rationale: "Im definierten Suchumfang wurde mit Rival AG eine funktional weitgehend vergleichbare Lösung identifiziert.",
    scope_summary: "Im definierten Suchumfang: 2 geprüfte öffentliche Quellen, 1 untersuchte Lösungskandidaten.",
    relevant_candidate_count: 1,
    key_overlaps: ["Erkennung", "Meldung"],
    evidenced_differentiators: [],
    plausible_unverified_differentiators: ["Zentralere Architektur (zu prüfen)."],
    open_evidence_gaps: ["Rival AG: Textstelle gefunden, inhaltlich noch nicht bestätigt."],
    allowed_formulations: ["Im definierten Suchumfang wurde mit Rival AG eine vergleichbare Lösung identifiziert."],
    disallowed_formulations: FORBIDDEN,
    can_insert_into_application: true,
    ...over,
  }
}

function comparison(over: Partial<MarketComparisonDto> = {}): MarketComparisonDto {
  return {
    comparison_id: "c1",
    project_id: "p1",
    status: "ready_for_review",
    comparison_version: 1,
    research_gaps: [],
    warnings: [],
    item_count: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    items: [],
    // Zwei geprüfte Quellen: erfüllt die Abdeckungsschwelle, ab der eine
    // Aussage überhaupt übernehmbar sein darf (marketUiState).
    source_version_ids: ["sv1", "sv2"],
    comparison_basis: {
      title: "Anomalieerkennung für KMU",
      idea: "Wir bauen eine automatisierte Qualitätsprüfung.",
      innovation_field: "Industrie 4.0",
      search_focus: "Öffentliche Lösungen zur Anomalieerkennung",
      search_aspects: ["Qualitätssicherung", "Schweiz"],
    },
    market_picture: {
      size_and_growth: [{ label: "Branchenstudie", value: "wachsender Markt" }],
      segments: [{ label: "Rival AG", value: "Schweizer KMU" }],
      trends: [],
      demand_indicators: [],
      swiss_relevance: [],
      gaps: [],
    },
    solution_landscape: {
      candidates: [candidate()],
      candidate_count_by_type: { direct_competitor: 1 },
    },
    competition_judgment: judgment(),
    scope_stale: false,
    ...over,
  }
}

function renderSheet(dto: MarketComparisonDto, onInsertText = vi.fn()) {
  render(
    <MarketComparisonSheet open onOpenChange={vi.fn()} comparison={dto} onInsertText={onInsertText} />
  )
  return onInsertText
}

describe("MarketComparisonSheet", () => {
  it("gliedert sich in genau drei Abschnitte: Ergebnis, Gefundene Lösungen, Was noch fehlt", () => {
    renderSheet(comparison())
    expect(screen.getByTestId("market-result")).toHaveTextContent("Ergebnis")
    expect(screen.getByTestId("market-solutions")).toHaveTextContent("Gefundene Lösungen")
    expect(screen.getByTestId("market-gaps-section")).toHaveTextContent("Was noch fehlt")
  })

  it("zeigt das Gesamturteil und trennt Marktbild von der Lösungslandschaft", () => {
    renderSheet(comparison())
    expect(screen.getByTestId("market-judgment")).toHaveTextContent(
      "Im definierten Suchumfang wurde mit Rival AG eine funktional weitgehend vergleichbare Lösung identifiziert."
    )
    const picture = screen.getByTestId("market-picture")
    const landscape = screen.getByTestId("market-solution-landscape")
    expect(picture).toBeInTheDocument()
    expect(landscape).toBeInTheDocument()
    // Kandidat erscheint in der Lösungslandschaft, nicht im Marktbild.
    expect(landscape).toHaveTextContent("Rival AG")
    expect(landscape).toHaveTextContent("Direkter Wettbewerber")
    expect(picture).not.toHaveTextContent("Direkter Wettbewerber")
  })

  it("fügt nur zulässige, quellenqualifizierte Aussagen ein", () => {
    const onInsertText = renderSheet(comparison())
    const btns = screen.getAllByRole("button", { name: "Übernehmen" })
    fireEvent.click(btns[0])
    expect(onInsertText).toHaveBeenCalledTimes(1)
    const inserted = onInsertText.mock.calls[0][0] as string
    expect(inserted).toContain("Im definierten Suchumfang")
    expect(inserted).toContain("gestützt auf")
  })

  // Bei ungenügender Abdeckung wird gar nichts zur Übernahme angeboten — ein
  // deaktivierter Button lädt zum Nachfassen ein, ein fehlender nicht.
  it("bietet bei can_insert_into_application=false keine Übernahme an", () => {
    renderSheet(comparison({ competition_judgment: judgment({ can_insert_into_application: false }) }))
    expect(screen.queryByRole("button", { name: "Übernehmen" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Als Argument übernehmen" })).toBeNull()
    expect(screen.getByTestId("market-insert-blocked")).toBeInTheDocument()
  })

  // Der kritische Fall: zu schmale Basis darf keine «es gibt nichts
  // Gleichwertiges»-Aussage in den Antrag lassen.
  it("sperrt die Übernahme unter zwei geprüften Quellen", () => {
    renderSheet(comparison({ source_version_ids: ["sv1"] }))
    expect(screen.getByTestId("market-sheet-status")).toHaveTextContent("Weitere Recherche nötig")
    expect(screen.queryByRole("button", { name: "Übernehmen" })).toBeNull()
    expect(screen.queryByTestId("market-allowed-formulations")).toBeNull()
    expect(screen.getByTestId("market-insert-blocked")).toBeInTheDocument()
  })

  it("sperrt die Übernahme bei veraltetem Suchraum", () => {
    renderSheet(comparison({ scope_stale: true }))
    expect(screen.getByTestId("market-sheet-status")).toHaveTextContent("Veraltet — neu erstellen")
    expect(screen.queryByRole("button", { name: "Übernehmen" })).toBeNull()
  })

  it("zeigt unzulässige Aussagen als Sperr-Block und rendert nie verbotene Phrasen als Antragstext", () => {
    renderSheet(comparison())
    const block = screen.getByTestId("market-disallowed")
    for (const phrase of FORBIDDEN) {
      expect(block).toHaveTextContent(phrase)
    }
  })

  // Die Sperrliste ist generisch und immer gleich — sie darf das Ergebnis nicht
  // verdrängen, muss aber einen Klick entfernt vollständig lesbar bleiben.
  it("hält die generische Sperrliste zugeklappt, ohne sie zu verstecken", () => {
    renderSheet(comparison())
    const block = screen.getByTestId("market-disallowed")
    expect(block.tagName).toBe("DETAILS")
    expect(block).not.toHaveAttribute("open")
    expect(block).toHaveTextContent("Nicht zulässige Aussagen")
    expect(block).toHaveTextContent(`(${FORBIDDEN.length})`)
  })

  // Derselbe Satz stand zuvor zweimal im Dialog: als Ergebnis und als
  // «zulässige Aussage» (R2 — eine Information je Ansicht genau einmal).
  it("wiederholt den Ergebnissatz nicht als zulässige Aussage", () => {
    const sentence =
      "Im definierten Suchumfang wurden keine öffentlich dokumentierten Lösungen identifiziert."
    const onInsertText = renderSheet(
      comparison({
        competition_judgment: judgment({
          rationale: sentence,
          allowed_formulations: [sentence],
        }),
      })
    )
    expect(screen.getAllByText(sentence)).toHaveLength(1)
    fireEvent.click(screen.getByRole("button", { name: "Übernehmen" }))
    expect(onInsertText.mock.calls[0][0] as string).toContain(sentence)
  })

  it("enthält keine Prozentwerte für Einzigartigkeit/Ähnlichkeit", () => {
    const { container } = render(
      <MarketComparisonSheet open onOpenChange={vi.fn()} comparison={comparison()} onInsertText={vi.fn()} />
    )
    // Kein Uniqueness-/Similarity-Prozent im Urteil/der Landschaft.
    expect(screen.getByTestId("market-judgment").textContent).not.toMatch(/\d\s?%/)
    expect(screen.getByTestId("market-solution-landscape").textContent).not.toMatch(/\d\s?%/)
    expect(container).toBeTruthy()
  })

  it("trennt belegte von plausibel-ungeprüfter Differenzierung", () => {
    renderSheet(
      comparison({
        competition_judgment: judgment({
          evidenced_differentiators: ["Belegte Abgrenzung."],
          plausible_unverified_differentiators: ["Plausibel, aber ungeprüft."],
        }),
      })
    )
    const card = screen.getByTestId("market-judgment")
    expect(card).toHaveTextContent("Belegte Differenzierung")
    expect(card).toHaveTextContent("Plausibel, aber noch ungeprüft")
  })

  // Ohne Lösungskandidaten ist der Grund «nur Marktinformationen» — nicht eine
  // fehlende menschliche Bestätigung (die das Backend gar nicht verlangt).
  it("nennt bei «Quellenlage noch nicht ausreichend» ohne Kandidaten den Marktinfo-Grund", () => {
    renderSheet(
      comparison({
        solution_landscape: { candidates: [], candidate_count_by_type: {} },
        competition_judgment: judgment({
          status: "insufficient_evidence",
          allowed_formulations: [],
          can_insert_into_application: false,
        }),
      })
    )
    expect(screen.getByTestId("market-sheet-status")).toHaveTextContent("Weitere Recherche nötig")
    expect(screen.getByTestId("market-insert-blocked")).toBeInTheDocument()
  })

  it("nennt bei unbelegten Kandidaten die fehlende Fundstelle als Grund", () => {
    renderSheet(
      comparison({
        solution_landscape: {
          candidates: [candidate({ confidence_label: "needs_review" })],
          candidate_count_by_type: { direct_competitor: 1 },
        },
        competition_judgment: judgment({
          status: "insufficient_evidence",
          allowed_formulations: [],
          can_insert_into_application: false,
        }),
      })
    )
    expect(screen.getByTestId("market-sheet-status")).toHaveTextContent("Weitere Recherche nötig")
    expect(screen.queryByRole("button", { name: "Als Argument übernehmen" })).toBeNull()
  })

  it("macht Veraltung zum Status statt zu einem Zusatz-Badge", () => {
    renderSheet(comparison({ scope_stale: true }))
    expect(screen.getByTestId("market-sheet-status")).toHaveTextContent("Veraltet — neu erstellen")
  })

  it("zeigt die Projektidee als Vergleichsbasis mit Suchfokus und Bearbeiten-Link", () => {
    renderSheet(comparison())
    const basis = screen.getByTestId("market-basis")
    // Kontext, nicht Ergebnis: zugeklappt, Titelzeile nennt Projekt und Feld.
    expect(basis.tagName).toBe("DETAILS")
    expect(basis).not.toHaveAttribute("open")
    expect(basis).toHaveTextContent("Vergleichsbasis")
    expect(basis).toHaveTextContent("Anomalieerkennung für KMU")
    expect(basis).toHaveTextContent("Wir bauen eine automatisierte Qualitätsprüfung.")
    expect(basis).toHaveTextContent("Öffentliche Lösungen zur Anomalieerkennung")
    expect(basis).toHaveTextContent("Qualitätssicherung")
    const editLink = screen.getByRole("button", { name: /Projektidee bearbeiten/ })
    expect(editLink).toHaveAttribute("href", "/intake")
  })

  it("blendet die Vergleichsbasis aus, wenn das Backend keine liefert", () => {
    renderSheet(comparison({ comparison_basis: null }))
    expect(screen.queryByTestId("market-basis")).toBeNull()
  })

  // UI-Bereinigung B1: `open_evidence_gaps` ist im Backend eine Obermenge von
  // `research_gaps` — beide zu rendern zeigte dieselbe Lücke zweimal im Dialog.
  // Der Abschnittskopf «Was noch fehlt» benennt die Liste; ein zweiter Titel
  // («Offene Evidenzlücken») direkt darunter entfällt.
  it("zeigt die offenen Evidenzlücken genau einmal, unter einer Überschrift", () => {
    const shared = "Rival AG: Textstelle gefunden, inhaltlich noch nicht bestätigt."
    renderSheet(comparison({ research_gaps: [shared] }))
    expect(screen.getAllByText("Was noch fehlt")).toHaveLength(1)
    expect(screen.queryByText("Offene Evidenzlücken")).toBeNull()
    expect(screen.getAllByText(shared)).toHaveLength(1)
  })

  // UI-Bereinigung B2: Marktaussagen sind keine Lösungskandidaten und dürfen
  // nie unter «Wettbewerber / Lösung» erscheinen.
  it("stellt Marktaussagen nie als Wettbewerber dar", () => {
    const marketClaim = {
      item_id: "mc-1",
      name: "Swiss biotech sector revenue 2023",
      category: "market_size_claim" as const,
      relation: "unclear" as const,
      short_description: "Umsatz des Schweizer Biotech-Sektors.",
      differentiation_relevance: null,
      evidence_quotes: [],
      source_document_ids: ["s1"],
      status: "proposed" as const,
      confidence_label: "source_backed" as const,
    }
    renderSheet(
      comparison({
        items: [marketClaim as never],
        solution_landscape: { candidates: [], candidate_count_by_type: {} },
      })
    )
    expect(screen.queryByText("Wettbewerber / Lösung")).toBeNull()
    expect(screen.queryByText("Swiss biotech sector revenue 2023")).toBeNull()
    expect(screen.getByTestId("market-only-claims")).toBeInTheDocument()
  })
})
