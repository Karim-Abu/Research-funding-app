import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { placeholderMatches } from "@/lib/draft-view"

vi.mock(
  "@/components/editor/rich-text-editor",
  async () => await import("./mocks/rich-text-editor")
)

import { LiveEditor } from "@/components/editor/live-editor"

describe("placeholderMatches", () => {
  it("returns the ranges of all placeholder variants in order", () => {
    const text = "Start [[Angabe ergänzen: X]] Mitte TODO und Angabe ergänzen Ende"
    const matches = placeholderMatches(text)
    expect(matches).toHaveLength(3)
    expect(text.slice(matches[0].start, matches[0].end)).toBe("[[Angabe ergänzen: X]]")
    expect(text.slice(matches[1].start, matches[1].end)).toBe("TODO")
    expect(text.slice(matches[2].start, matches[2].end)).toBe("Angabe ergänzen")
  })

  it("returns an empty list for clean text", () => {
    expect(placeholderMatches("Fertiger Text ohne offene Angaben.")).toEqual([])
  })
})

const TWO_PLACEHOLDERS =
  "3.1 Beschreibung [[Angabe ergänzen: Ziele]]\n\n3.2 Kunden [[Angabe ergänzen: Segment]]"

function draft(text: string) {
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
      created_at: new Date().toISOString(),
      content_hash: "h",
    },
    character_count: text.length,
    character_limit: 300,
    open_issue_count: 0,
    evidence_links: [],
    open_issues: [],
  }
}

function mock(text: string) {
  server.use(
    http.get("/api/runs/r1/fields", () => HttpResponse.json([draft(text)])),
    http.get("/api/runs/r1/evidence", () => HttpResponse.json([])),
    http.get("/api/runs/r1/requirements", () => HttpResponse.json([])),
    http.get("/api/runs/r1/review", () =>
      HttpResponse.json({
        run_id: "r1",
        requirements: [],
        fields: [],
        findings: [],
        approval_status: "blocked",
        blocker_count: 0,
        warning_count: 0,
        open_issues: [],
        review_package_version: "rpv",
        current_approval_scope_hash: "h".repeat(64),
        recheck_required: false,
        stale_finding_count: 0,
      })
    )
  )
}

describe("placeholder banner cycling", () => {
  it("shows the count and cycles the selection through all placeholders", async () => {
    mock(TWO_PLACEHOLDERS)
    render(<LiveEditor runId="r1" />)
    const textarea = (await screen.findByLabelText(
      "Entwurf Abstract"
    )) as HTMLTextAreaElement

    expect(screen.getByText("2 offene Angaben im Text.")).toBeInTheDocument()
    const next = screen.getByRole("button", { name: "Nächster Platzhalter" })
    const matches = placeholderMatches(TWO_PLACEHOLDERS)

    fireEvent.click(next)
    await waitFor(() => expect(textarea.selectionStart).toBe(matches[0].start))
    expect(textarea.selectionEnd).toBe(matches[0].end)

    fireEvent.click(next)
    await waitFor(() => expect(textarea.selectionStart).toBe(matches[1].start))
    expect(textarea.selectionEnd).toBe(matches[1].end)
  })

  it("offers 'Platzhalter markieren' when only one placeholder exists", async () => {
    mock("Text mit einem TODO in der Mitte.")
    render(<LiveEditor runId="r1" />)
    await screen.findByLabelText("Entwurf Abstract")
    expect(screen.getByText("1 offene Angabe im Text.")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Platzhalter markieren" })
    ).toBeInTheDocument()
  })
})
