// 2026-07-24 — Viewmodels für die Markt-Oberflächen: EIN ehrlicher Status
// (kein «Fehlgeschlagen» + «Nicht analysiert» gleichzeitig) und ein Marktbild,
// das nur aus quellengestützten Einträgen abgeleitet wird.
import { describe, it, expect } from "vitest"

import {
  candidateTypeLabel,
  deriveMarketPicture,
  judgmentToneClass,
  marketGaps,
  marketPictureFrom,
  marketWorkspaceStatus,
} from "@/lib/market-view"
import type {
  ItemCategory,
  ConfidenceLabel,
  MarketComparisonDto,
  MarketComparisonItemDto,
} from "@/lib/market-comparison"

function item(
  overrides: Partial<MarketComparisonItemDto> & {
    category: ItemCategory
    confidence_label: ConfidenceLabel
  }
): MarketComparisonItemDto {
  return {
    item_id: Math.random().toString(36).slice(2),
    name: "Eintrag",
    relation_to_project: "unclear",
    status: "proposed",
    source_document_ids: ["s1"],
    evidence_quotes: [],
    ...overrides,
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
    item_count: 0,
    created_at: "2026-07-24T00:00:00Z",
    updated_at: "2026-07-24T00:00:00Z",
    items: [],
    ...overrides,
  }
}

describe("marketWorkspaceStatus", () => {
  it("liefert einen neutralen Zustand ohne Vergleich", () => {
    expect(marketWorkspaceStatus(null)).toEqual({
      label: "Noch nicht erstellt",
      tone: "neutral",
    })
  })

  it("zeigt failed als Fehlversuch mit Retry-Hinweis (nie «Nicht analysiert»)", () => {
    const status = marketWorkspaceStatus(comparison({ status: "failed" }))
    expect(status.label).toBe("Letzter Versuch fehlgeschlagen")
    expect(status.tone).toBe("error")
    expect(status.hint).toMatch(/erneut/i)
  })

  it("benennt zu wenige geprüfte Quellen", () => {
    expect(
      marketWorkspaceStatus(comparison({ status: "insufficient_external_evidence" })).label
    ).toBe("Zu wenige geprüfte Quellen")
  })

  it("ist erst mit Einträgen «Zur Prüfung bereit», sonst ehrlich leer", () => {
    const withItems = marketWorkspaceStatus(
      comparison({
        status: "ready_for_review",
        items: [item({ category: "competitor", confidence_label: "source_backed" })],
      })
    )
    expect(withItems).toEqual({ label: "Zur Prüfung bereit", tone: "positive" })

    const withoutItems = marketWorkspaceStatus(
      comparison({ status: "ready_for_review", items: [] })
    )
    expect(withoutItems.label).toBe("Keine belegten Einträge")
    expect(withoutItems.tone).toBe("attention")
  })
})

describe("deriveMarketPicture", () => {
  it("leitet Lösungsarten, Kundengruppen und Marktsignale nur aus belegten Einträgen ab", () => {
    const picture = deriveMarketPicture(
      comparison({
        research_gaps: ["Keine direkten Wettbewerber belegt."],
        items: [
          item({
            category: "reference_solution",
            confidence_label: "source_backed",
            name: "BioMedIT",
            target_customer_segment: "Akademische Forschende",
          }),
          item({
            category: "reference_solution",
            confidence_label: "source_backed",
            name: "TRE",
            target_customer_segment: "Gesundheitsforschung",
          }),
          item({
            category: "market_size_claim",
            confidence_label: "source_backed",
            name: "Markt wächst mit 9,3% CAGR",
          }),
          // needs_review darf NICHT ins Marktbild einfliessen.
          item({
            category: "competitor",
            confidence_label: "needs_review",
            name: "Unbelegter Konkurrent",
          }),
        ],
      })
    )
    const labels = picture.points.map((p) => p.label)
    expect(labels).toContain("Lösungsarten")
    expect(labels).toContain("Kundengruppen")
    expect(labels).toContain("Marktsignale")

    const loesungsarten = picture.points.find((p) => p.label === "Lösungsarten")
    expect(loesungsarten?.value).toContain("Referenzlösung (2)")
    expect(loesungsarten?.value).not.toContain("Konkurrent")

    const signale = picture.points.find((p) => p.label === "Marktsignale")
    expect(signale?.value).toContain("Markt wächst mit 9,3% CAGR")

    expect(picture.gaps).toEqual(["Keine direkten Wettbewerber belegt."])
    expect(picture.hasContent).toBe(true)
  })

  it("ist leer ohne Vergleich oder ohne belegte Einträge/Lücken", () => {
    expect(deriveMarketPicture(null).hasContent).toBe(false)
    expect(deriveMarketPicture(comparison()).hasContent).toBe(false)
  })
})

describe("marketPictureFrom", () => {
  it("bevorzugt das Backend-Marktbild, wenn vorhanden", () => {
    const picture = marketPictureFrom(
      comparison({
        market_picture: {
          size_and_growth: [{ label: "Studie", value: "wächst" }],
          segments: [{ label: "A", value: "KMU" }],
          trends: [],
          demand_indicators: [],
          swiss_relevance: [],
          gaps: ["Lücke"],
        },
      })
    )
    const labels = picture.points.map((p) => p.label)
    expect(labels).toContain("Marktgrösse & Wachstum")
    expect(labels).toContain("Segmente")
    expect(picture.gaps).toEqual(["Lücke"])
  })

  it("fällt ohne Backend-Marktbild auf die Client-Ableitung zurück", () => {
    const picture = marketPictureFrom(
      comparison({
        items: [item({ category: "competitor", confidence_label: "source_backed", name: "X" })],
      })
    )
    expect(picture.points.some((p) => p.label === "Lösungsarten")).toBe(true)
  })

  // UI-Bereinigung: dieselbe Fundstelle trägt oft mehrere Rubriken. Ohne
  // zeilenübergreifende Dedupe standen wortgleiche Zeilen untereinander.
  it("zeigt denselben Wert nicht in zwei Rubriken", () => {
    const fragment = "Fragment nennt einen Umsatzwert für den Schweizer Biotech-Sektor 2023."
    const picture = marketPictureFrom(
      comparison({
        market_picture: {
          size_and_growth: [{ label: "Studie", value: fragment }],
          segments: [],
          trends: [],
          demand_indicators: [{ label: "Studie", value: fragment }],
          swiss_relevance: [],
          gaps: [],
        },
      })
    )
    const labels = picture.points.map((p) => p.label)
    expect(labels).toEqual(["Marktgrösse & Wachstum"])
    expect(labels).not.toContain("Nachfrage")
  })

  it("behält eine Rubrik, sobald sie einen eigenen Wert trägt", () => {
    const shared = "Gemeinsames Fragment."
    const picture = marketPictureFrom(
      comparison({
        market_picture: {
          size_and_growth: [{ label: "A", value: shared }],
          segments: [],
          trends: [],
          demand_indicators: [
            { label: "A", value: shared },
            { label: "B", value: "Eigener Nachfragewert." },
          ],
          swiss_relevance: [],
          gaps: [],
        },
      })
    )
    const demand = picture.points.find((p) => p.label === "Nachfrage")
    expect(demand?.value).toBe("Eigener Nachfragewert.")
  })
})

describe("marketGaps", () => {
  it("nutzt die Urteilsliste (Obermenge) statt beide Listen zu mischen", () => {
    const dto = comparison({
      research_gaps: ["Basis-Lücke"],
      competition_judgment: {
        status: "insufficient_evidence",
        rationale: "r",
        scope_summary: "s",
        relevant_candidate_count: 0,
        key_overlaps: [],
        evidenced_differentiators: [],
        plausible_unverified_differentiators: [],
        open_evidence_gaps: ["Basis-Lücke", "Zusatz-Lücke"],
        allowed_formulations: [],
        disallowed_formulations: [],
        can_insert_into_application: false,
      },
    })
    expect(marketGaps(dto)).toEqual(["Basis-Lücke", "Zusatz-Lücke"])
  })

  it("fällt auf research_gaps zurück, wenn das Urteil keine Lücken führt", () => {
    expect(marketGaps(comparison({ research_gaps: ["Nur hier"] }))).toEqual(["Nur hier"])
    expect(marketGaps(null)).toEqual([])
  })
})

describe("candidateTypeLabel / judgmentToneClass", () => {
  it("übersetzt Kandidatentypen und liefert Ton-Klassen", () => {
    expect(candidateTypeLabel("direct_competitor")).toBe("Direkter Wettbewerber")
    expect(candidateTypeLabel("open_source_solution")).toBe("Open-Source-Lösung")
    expect(judgmentToneClass("no_direct_equivalent_in_scope")).toContain("status-fulfilled")
    expect(judgmentToneClass("insufficient_evidence")).toContain("muted")
  })
})
