import { describe, expect, it } from "vitest"
import { placeholderMatches } from "@/lib/draft-view"
import { fieldReadinessRows } from "@/lib/export-view"
import type { PortalFieldDraftDto } from "@/lib/fields"
import { countPlaceholders, fieldWarnings, hasPlaceholder } from "@/lib/portal-transfer"
import type { ReviewPackageDto } from "@/lib/review"

function field(text: string): PortalFieldDraftDto {
  return {
    draft_id: "d1",
    field_id: "INTRO.APP.ABSTRACT",
    field_name: "Abstract",
    status: "needs_review",
    current_version: {
      draft_version_id: "v1",
      text,
      character_count: text.length,
      created_by: "template",
      created_at: new Date("2026-07-05T10:00:00Z").toISOString(),
      content_hash: "h",
    },
    character_count: text.length,
    character_limit: 300,
    open_issue_count: 0,
    evidence_links: [],
    open_issues: [],
  }
}

function reviewPkg(): ReviewPackageDto {
  return {
    run_id: "r1",
    requirements: [],
    fields: [],
    findings: [],
    approval_status: "approved",
    blocker_count: 0,
    warning_count: 0,
    open_issues: [],
    review_package_version: "rpv-1",
    current_approval_scope_hash: "h".repeat(64),
    recheck_required: false,
    stale_finding_count: 0,
  }
}

describe("strict placeholder helpers", () => {
  it.each([
    ["TODO", false],
    ["tbd", false],
    ["[[anderer Platzhalter]]", false],
    ["[[Angabe ergänzen: X]]", true],
  ])("matches backend placeholder syntax for %s", (text, expected) => {
    expect(hasPlaceholder(text)).toBe(expected)
  })

  it("counts only strict placeholders and has no global test state", () => {
    const strict = "[[Angabe ergänzen: X]]"
    const mixed = `${strict} TODO tbd [[anderer Platzhalter]]`
    expect(countPlaceholders(mixed)).toBe(1)
    expect(hasPlaceholder(strict)).toBe(true)
    expect(hasPlaceholder(strict)).toBe(true)
    expect(hasPlaceholder("TODO")).toBe(false)
    expect(hasPlaceholder(strict)).toBe(true)
  })

  it("keeps broad draft-view placeholder matching for editor jump UX", () => {
    const text = "TODO und tbd neben [[anderer Platzhalter]]"
    const matches = placeholderMatches(text).map((match) =>
      text.slice(match.start, match.end)
    )
    expect(matches).toEqual(["TODO", "tbd", "[[anderer Platzhalter]]"])
  })

  it("uses strict placeholders for portal warnings and export readiness", () => {
    const review = reviewPkg()
    expect(fieldWarnings(field("TODO"), review)).toEqual([])
    expect(fieldWarnings(field("[[Angabe ergänzen: X]]"), review)).toEqual([
      { code: "open", message: "Dieser Feldtext enthält noch offene Angaben." },
    ])
    expect(fieldReadinessRows([field("TODO")], review)[0].status).toBe(
      "kopierbereit"
    )
    expect(
      fieldReadinessRows([field("[[Angabe ergänzen: X]]")], review)[0].status
    ).toBe("platzhalter_offen")
  })
})