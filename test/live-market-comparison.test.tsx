// RUN 4B §8 — kompakte Markt-Ansicht im Editor: Status + Anzahl geprüfter
// Quellen, höchstens drei Findings, ehrliche limited-ohne-Items-Copy,
// keine zweite Analyse (nur Link/Öffnen).
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
  it("zeigt Status, Anzahl geprüfter Quellen und höchstens drei Findings", () => {
    render(
      <LiveMarketComparison
        comparison={comparison()}
        loaded
        onOpenComparison={vi.fn()}
      />
    )
    // Dedupliziert: 4 Einträge über 2 Quellen.
    expect(screen.getByText("2 geprüfte Quellen")).toBeInTheDocument()
    // Höchstens drei Findings, der vierte Eintrag erscheint nicht.
    expect(screen.getByText("Anbieter i1")).toBeInTheDocument()
    expect(screen.getByText("Anbieter i3")).toBeInTheDocument()
    expect(screen.queryByText("Anbieter i4")).toBeNull()
    // Arbeitsfläche nur über den Link — kein Generate-Button im Editor.
    expect(
      screen.getByRole("button", { name: "Marktvergleich öffnen" })
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
      screen.getByRole("button", { name: "Marktvergleich öffnen" })
    ).toBeDisabled()
  })

  it("ohne Vergleich: neutraler Leerzustand mit Quellen-Link", () => {
    render(<LiveMarketComparison comparison={null} loaded />)
    expect(screen.getByTestId("market-editor-empty")).toHaveTextContent(
      "Noch kein belegter Markt- und Konkurrenzvergleich."
    )
  })
})
