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
  it("zeigt das Gesamturteil und trennt Marktbild von der Lösungslandschaft", () => {
    renderSheet(comparison())
    expect(screen.getByTestId("market-judgment")).toBeInTheDocument()
    expect(screen.getByText("Direkt vergleichbare Lösung gefunden")).toBeInTheDocument()
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

  it("sperrt das Einfügen bei can_insert_into_application=false", () => {
    renderSheet(comparison({ competition_judgment: judgment({ can_insert_into_application: false }) }))
    for (const btn of screen.getAllByRole("button", { name: "Übernehmen" })) {
      expect(btn).toBeDisabled()
    }
  })

  it("zeigt unzulässige Aussagen als Sperr-Block und rendert nie verbotene Phrasen als Antragstext", () => {
    renderSheet(comparison())
    const block = screen.getByTestId("market-disallowed")
    for (const phrase of FORBIDDEN) {
      expect(block).toHaveTextContent(phrase)
    }
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

  it("zeigt einen Stale-Hinweis getrennt vom Runtime-Status", () => {
    renderSheet(comparison({ scope_stale: true }))
    expect(screen.getByTestId("market-sheet-stale")).toHaveTextContent("Suchraum geändert")
  })

  it("zeigt die Projektidee als Vergleichsbasis mit Suchfokus und Bearbeiten-Link", () => {
    renderSheet(comparison())
    const basis = screen.getByTestId("market-basis")
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
})
