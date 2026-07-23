// RUN 4B §9 — Wiederherstellen über den bestehenden Versionspfad:
// Alttext lesen → regulärer PATCH → neue user-Version; No-op bei identischem
// Text; gesperrt bei ungespeicherten Änderungen.
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"

vi.mock(
  "@/components/editor/rich-text-editor",
  async () => await import("./mocks/rich-text-editor")
)

import { LiveEditor } from "@/components/editor/live-editor"

const ABSTRACT = "INTRO.APP.ABSTRACT"
const OLD_TEXT = "Ursprünglicher Abstract-Text."
const NEW_TEXT = "Aktueller, überarbeiteter Abstract-Text."

function version(id: string, text: string, createdBy: string) {
  return {
    draft_version_id: id,
    text,
    character_count: [...text].length,
    created_by: createdBy,
    created_at: "2026-07-01T09:30:00Z",
    content_hash: `h-${id}`,
  }
}

function draft(currentId = "v2", text = NEW_TEXT) {
  return {
    draft_id: "d1",
    field_id: ABSTRACT,
    field_name: "Abstract",
    status: "needs_review",
    current_version: version(currentId, text, "user"),
    character_count: [...text].length,
    character_limit: 300,
    open_issue_count: 0,
    evidence_links: [],
    open_issues: [],
  }
}

function summaries(currentId: string, count: number) {
  const rows = [
    {
      draft_version_id: currentId,
      created_at: "2026-07-02T10:00:00Z",
      created_by: "user",
      generation_kind: null,
      character_count: 40,
      is_current: true,
    },
    {
      draft_version_id: "v1",
      created_at: "2026-07-01T09:30:00Z",
      created_by: "template",
      generation_kind: "rule_template",
      character_count: [...OLD_TEXT].length,
      is_current: false,
    },
  ]
  if (count > 2) {
    rows.unshift({
      draft_version_id: "v3",
      created_at: "2026-07-03T11:00:00Z",
      created_by: "user",
      generation_kind: null,
      character_count: [...OLD_TEXT].length,
      is_current: true,
    })
    rows[1].is_current = false
  }
  return { versions: rows.slice(0, count === 2 ? 2 : 3) }
}

function reviewPkg() {
  return {
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
  }
}

function baseHandlers() {
  server.use(
    http.get("/api/runs/r1/fields", () => HttpResponse.json([draft()])),
    http.get("/api/runs/r1/evidence", () => HttpResponse.json([])),
    http.get("/api/runs/r1/requirements", () => HttpResponse.json([])),
    http.get("/api/runs/r1/fields/:field/suggestion", () =>
      HttpResponse.json({ suggestion: null })
    ),
    http.get("/api/runs/r1/review", () => HttpResponse.json(reviewPkg()))
  )
}

describe("LiveEditor — Versionshistorie und Wiederherstellen", () => {
  it("stellt eine Altversion über den bestehenden PATCH-Pfad wieder her", async () => {
    baseHandlers()
    let versionCalls = 0
    let patchBody: Record<string, unknown> | null = null
    server.use(
      http.get(`/api/runs/r1/fields/${ABSTRACT}/versions`, () => {
        versionCalls += 1
        return HttpResponse.json(summaries("v2", versionCalls > 1 ? 3 : 2))
      }),
      http.get(`/api/runs/r1/fields/${ABSTRACT}/versions/v1`, () =>
        HttpResponse.json({
          ...version("v1", OLD_TEXT, "template"),
          generation_kind: "rule_template",
        })
      ),
      http.patch(`/api/runs/r1/fields/${ABSTRACT}`, async ({ request }) => {
        patchBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(draft("v3", OLD_TEXT))
      })
    )
    render(<LiveEditor runId="r1" />)
    await screen.findByLabelText("Entwurf Abstract")
    fireEvent.click(screen.getByRole("tab", { name: "Versionen" }))

    const rows = await screen.findAllByTestId("version-row")
    fireEvent.click(
      within(rows[1]).getByRole("button", { name: "Wiederherstellen" })
    )

    await waitFor(() =>
      expect(
        screen.getByText(
          "Frühere Version wiederhergestellt und als neue Version gespeichert."
        )
      ).toBeInTheDocument()
    )
    // Bestehender Versionspfad: Base = bisherige aktuelle Version, Text = Altversion.
    expect(patchBody).toMatchObject({ base_version_id: "v2", text: OLD_TEXT })
    // (Die Editor-Übernahme des Server-Texts deckt der Playwright-E2E ab —
    // der Test-Stub re-seedet nur bei Feldwechsel.)
    // Liste wurde neu geladen (jetzt drei Versionen — nichts geht verloren).
    await waitFor(() =>
      expect(screen.getAllByTestId("version-row")).toHaveLength(3)
    )
  })

  it("identischer Text ist ein No-op ohne neue Version", async () => {
    baseHandlers()
    server.use(
      http.get(`/api/runs/r1/fields/${ABSTRACT}/versions`, () =>
        HttpResponse.json(summaries("v2", 2))
      ),
      http.get(`/api/runs/r1/fields/${ABSTRACT}/versions/v1`, () =>
        HttpResponse.json(version("v1", NEW_TEXT, "template"))
      ),
      // Server-No-op: identischer Text → dieselbe aktuelle Version zurück.
      http.patch(`/api/runs/r1/fields/${ABSTRACT}`, () =>
        HttpResponse.json(draft("v2", NEW_TEXT))
      )
    )
    render(<LiveEditor runId="r1" />)
    await screen.findByLabelText("Entwurf Abstract")
    fireEvent.click(screen.getByRole("tab", { name: "Versionen" }))

    const rows = await screen.findAllByTestId("version-row")
    fireEvent.click(
      within(rows[1]).getByRole("button", { name: "Wiederherstellen" })
    )
    await waitFor(() =>
      expect(
        screen.getByText("Diese Version entspricht bereits dem aktuellen Text.")
      ).toBeInTheDocument()
    )
  })

  it("Wiederherstellen ist bei ungespeicherten Änderungen gesperrt und erklärt warum", async () => {
    baseHandlers()
    server.use(
      http.get(`/api/runs/r1/fields/${ABSTRACT}/versions`, () =>
        HttpResponse.json(summaries("v2", 2))
      )
    )
    render(<LiveEditor runId="r1" />)
    const editor = await screen.findByLabelText("Entwurf Abstract")
    fireEvent.change(editor, { target: { value: "Lokal geänderter Text" } })
    fireEvent.click(screen.getByRole("tab", { name: "Versionen" }))

    const rows = await screen.findAllByTestId("version-row")
    const restore = within(rows[1]).getByRole("button", {
      name: "Wiederherstellen",
    })
    expect(restore).toBeDisabled()
    expect(restore).toHaveAttribute(
      "title",
      "Bitte zuerst Ihre ungespeicherten Änderungen speichern oder verwerfen."
    )
  })
})
