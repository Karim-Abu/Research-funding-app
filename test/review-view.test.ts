import { describe, it, expect } from "vitest"
import {
  areaProgress,
  checkStateLabel,
  notRunReasonLabel,
  CHECK_AREA_LABELS,
  type CheckAreaKey,
  type CheckAreaStatusDto,
} from "@/lib/check-status"
import { humanReviewCount } from "@/lib/review-view"
import type { ReviewPackageDto } from "@/lib/review"

const AREAS = Object.keys(CHECK_AREA_LABELS) as CheckAreaKey[]

function area(
  key: CheckAreaKey,
  overrides: Partial<CheckAreaStatusDto> = {}
): CheckAreaStatusDto {
  return {
    area: key,
    status: "not_run",
    open_blockers: 0,
    open_warnings: 0,
    reason: "not_executed",
    ...overrides,
  }
}

describe("areaProgress (Bearbeitungs- und Prüfstand)", () => {
  it("ohne ausgeführte Checks ist NICHTS bestanden — alles «nicht geprüft»", () => {
    const progress = areaProgress(AREAS.map((k) => area(k)))
    expect(progress.total).toBe(AREAS.length)
    expect(progress.bestanden).toBe(0)
    expect(progress.nichtGeprueft).toBe(AREAS.length)
    expect(progress.teilweise).toBe(0)
    expect(progress.nichtBestanden).toBe(0)
  })

  it("die vier Segmente summieren sich immer zum Nenner", () => {
    const progress = areaProgress([
      area("pflichtfelder", { status: "passed", reason: null }),
      area("platzhalter", { status: "failed", open_blockers: 1, reason: null }),
      area("konsistenz", { status: "warning", open_warnings: 3, reason: null }),
      area("evidenz_coverage"),
    ])
    expect(progress.total).toBe(4)
    expect(progress.bestanden).toBe(1)
    expect(progress.nichtBestanden).toBe(1)
    expect(progress.teilweise).toBe(1)
    expect(progress.nichtGeprueft).toBe(1)
    expect(
      progress.bestanden +
        progress.teilweise +
        progress.nichtBestanden +
        progress.nichtGeprueft
    ).toBe(progress.total)
  })
})

describe("checkStateLabel (Statussprache)", () => {
  it("not_run heisst «Nicht geprüft» — nie «Bestanden»", () => {
    expect(checkStateLabel(area("evidenz_suffizienz"))).toBe("Nicht geprüft")
    expect(checkStateLabel(area("evidenz_coverage"))).not.toMatch(/Bestanden/)
  })

  it("Export mit Warnungen heisst «Mit Warnungen kopierbar», nie grün-bestanden", () => {
    expect(
      checkStateLabel(area("export", { status: "warning", reason: null }))
    ).toBe("Mit Warnungen kopierbar")
    expect(
      checkStateLabel(area("konsistenz", { status: "warning", reason: null }))
    ).toBe("Teilweise bestanden")
  })

  it("Gründe erscheinen nutzerlesbar, nie als roher Maschinen-Schlüssel", () => {
    expect(notRunReasonLabel(area("evidenz_suffizienz", { reason: "stale" }))).toMatch(
      /veraltet/
    )
    expect(notRunReasonLabel(area("evidenz_suffizienz"))).toMatch(
      /noch nicht ausgeführt/
    )
  })
})

describe("humanReviewCount", () => {
  it("zählt Anforderungen mit menschlichem Prüfbedarf ohne Overrides", () => {
    const pkg = {
      requirements: [
        { basis: "rules", status: "needs_input" },
        { basis: "rules", status: "partial" },
        { basis: "human_override", status: "open" },
        { basis: "rules", status: "fulfilled" },
      ],
    } as unknown as ReviewPackageDto
    expect(humanReviewCount(pkg)).toBe(2)
  })
})

describe("Kommentartypen (B5 Notizen)", () => {
  it("präfixiert und parst den Typ «Notiz»", async () => {
    const { commentWithType, parseCommentType, COMMENT_TYPES } = await import(
      "@/lib/review-view"
    )
    expect(COMMENT_TYPES).toContain("Notiz")
    const stored = commentWithType("Notiz", "Interne Überlegung zum Budget.")
    expect(stored).toBe("[Notiz] Interne Überlegung zum Budget.")
    expect(parseCommentType(stored)).toEqual({
      type: "Notiz",
      text: "Interne Überlegung zum Budget.",
    })
  })
})
