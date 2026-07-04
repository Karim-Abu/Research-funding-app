import { describe, it, expect } from "vitest"
import {
  groupFindings,
  reviewProgress,
  REVIEW_GROUP_ORDER,
  type ReviewFindingDto,
} from "@/lib/review-view"

function finding(overrides: Partial<ReviewFindingDto> = {}): ReviewFindingDto {
  return {
    finding_id: "f1",
    profile_id: "p",
    field_id: "INTRO.APP.ABSTRACT",
    requirement_id: null,
    severity: "blocker",
    description: "Feld enthält Platzhalter.",
    suggested_improvement: null,
    status: "open",
    advisory: false,
    ...overrides,
  } as ReviewFindingDto
}

describe("reviewProgress (Bearbeitungs- und Prüfstand)", () => {
  it("keeps the full denominator even without findings (ring invariant)", () => {
    const progress = reviewProgress(groupFindings([]))
    expect(progress.total).toBe(REVIEW_GROUP_ORDER.length)
    expect(progress.bestanden).toBe(REVIEW_GROUP_ORDER.length)
    expect(progress.teilweise).toBe(0)
    expect(progress.nichtBestanden).toBe(0)
  })

  it("classifies groups by their worst finding severity", () => {
    const progress = reviewProgress(
      groupFindings([
        // Blocker in the Platzhalter group → nicht bestanden.
        finding(),
        // Non-blocker hint in the Zeichenlimits group → teilweise bestanden.
        finding({
          finding_id: "f2",
          severity: "warning",
          description: "Der Text überschreitet das Zeichenlimit knapp.",
        }),
      ])
    )
    expect(progress.total).toBe(REVIEW_GROUP_ORDER.length)
    expect(progress.nichtBestanden).toBe(1)
    expect(progress.teilweise).toBe(1)
    expect(progress.bestanden).toBe(REVIEW_GROUP_ORDER.length - 2)
    // The three ring segments always sum to the denominator.
    expect(
      progress.bestanden + progress.teilweise + progress.nichtBestanden
    ).toBe(progress.total)
  })
})
