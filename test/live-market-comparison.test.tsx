// RUN 4B §8 — kompakte Markt-Ansicht im Editor: Status + drei Kennzahlen
// (Quellen/Lösungen/Lücken), ehrliche limited-ohne-Items-Copy, keine zweite
// Analyse (nur Link/Öffnen). Marktbild und Gesamturteil-Begründung liegen in
// der Detailansicht (market-comparison-sheet.test.tsx).
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { LiveMarketComparison } from "@/components/editor/live-market-comparison"
import type { MarketComparisonDto } from "@/lib/market-comparison"

function item(id: string, sourceId: string) {
  return {
    item_id: id,
    name: `Anbieter ${id}`,
    category: "competitor" as const,
    description: null,
    differentiation_relevance: "Öffentlich erwähnter Unterschied.",
    relation_to_project: "competing" as const,
    confidence_label: "source_backed" as const,
    status: "proposed" as const,
    source_document_ids: [sourceId],
    evidence_quotes: [
      {
        quote: `Zitat für ${id}.`,
        source_document_id: sourceId,
        source_version_id: "v1",
      },
    ],
  }
}

function comparison(
  overrides: Partial<MarketComparisonDto> = {}
): MarketComparisonDto {
  return {
    comparison_id: "c1",
    project_id: "p1",
    status: "ready_for_review",
    comparison_version: 1,
    research_gaps: [],
    warnings: [],
    item_count: 4,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    items: [
      item("i1", "s1"),
      item("i2", "s1"),
      item("i3", "s2"),
      item("i4", "s2"),
    ],
    ...overrides,
  }
}

describe("LiveMarketComparison (RUN 4B §8)", () => {
  it("zeigt Status und die drei Kennzahlen (Quellen, Lösungen, Lücken)", () => {
    render(
      <LiveMarketComparison
        comparison={comparison()}
        loaded
        onOpenComparison={vi.fn()}
      />
    )
    // Dedupliziert: 4 Einträge über 2 Quellen, alle 4 sind Lösungskandidaten.
    expect(screen.getByText("2 geprüfte Quellen")).toBeInTheDocument()
    expect(screen.getByText("4 Lösungen gefunden")).toBeInTheDocument()
    // Keine offenen Lücken → keine dritte Zeile.
    expect(screen.queryByText(/zentrale Lücke/)).toBeNull()
    // Arbeitsfläche nur über den Link — kein Generate-Button im Editor.
    expect(
      screen.getByRole("button", { name: "Details öffnen" })
    ).toBeInTheDocument()
    expect(screen.queryByText(/Vergleich erstellen/)).toBeNull()
  })

  it("limited ohne Einträge erscheint nie als leerer Erfolg", () => {
    render(
      <LiveMarketComparison
        comparison={comparison({ status: "limited", items: [], item_count: 0 })}
        loaded
        onOpenComparison={vi.fn()}
      />
    )
    expect(screen.getByTestId("market-editor-empty")).toHaveTextContent(
      "Marktinformationen vorhanden, aber noch kein belastbarer Anbieter-/Alternativenvergleich."
    )
    // Ohne Einträge bleibt die Tabelle zu; der Öffnen-Button erklärt warum.
    expect(
      screen.getByRole("button", { name: "Details öffnen" })
    ).toBeDisabled()
  })

  // Marktstatistiken sind keine Wettbewerber — auch nicht in der kompakten Rail.
  it("führt Marktaussagen nicht als Wettbewerbs-Findings", () => {
    const claim = {
      ...item("m1", "s1"),
      name: "Marktwachstum 2032",
      category: "market_size_claim" as const,
    }
    render(
      <LiveMarketComparison
        comparison={comparison({ items: [claim], item_count: 1 })}
        loaded
        onOpenComparison={vi.fn()}
      />
    )
    // Erzeugt keine Kennzahlen-/Findings-Anzeige, sondern eine ehrliche Leerzeile.
    expect(screen.getByTestId("market-editor-empty")).toHaveTextContent(
      "Bisher nur Marktinformationen gefunden, noch keine vergleichbaren Lösungen."
    )
    expect(screen.queryByTestId("market-editor-summary")).toBeNull()
  })

  it("ohne Vergleich: neutraler Leerzustand mit Quellen-Link", () => {
    render(<LiveMarketComparison comparison={null} loaded />)
    expect(screen.getByTestId("market-editor-empty")).toHaveTextContent(
      "Noch kein belegter Markt- und Konkurrenzvergleich."
    )
  })

  // 2026-07-24 — failed zeigt einen ehrlichen Fehlversuch (nie «Nicht
  // analysiert») samt sichtbarem Grund am deaktivierten Öffnen-Button.
  it("failed: einheitlicher Fehlversuch-Status + sichtbarer Öffnen-Grund", () => {
    render(
      <LiveMarketComparison
        comparison={comparison({ status: "failed", items: [], item_count: 0 })}
        loaded
        onOpenComparison={vi.fn()}
      />
    )
    expect(screen.getByTestId("market-editor-status")).toHaveTextContent(
      "Erstellung fehlgeschlagen"
    )
    expect(screen.queryByText("Nicht analysiert")).toBeNull()
    expect(
      screen.getByRole("button", { name: "Details öffnen" })
    ).toBeDisabled()
    expect(
      screen.getByTestId("market-editor-open-disabled-reason")
    ).toHaveTextContent("Letzter Versuch fehlgeschlagen — unter Quellen erneut erstellen.")
  })

  it("zeigt eine Lücken-Kennzahl, wenn offene Evidenzlücken bestehen", () => {
    render(
      <LiveMarketComparison
        comparison={comparison({ research_gaps: ["Eine offene Lücke."] })}
        loaded
        onOpenComparison={vi.fn()}
      />
    )
    expect(screen.getByText("1 zentrale Lücke")).toBeInTheDocument()
  })
})
