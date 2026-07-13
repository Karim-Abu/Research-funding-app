import { describe, it, expect, afterEach, vi } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"

vi.mock(
  "@/components/editor/rich-text-editor",
  async () => await import("./mocks/rich-text-editor")
)

import { LiveEditor } from "@/components/editor/live-editor"

const ABSTRACT = "INTRO.APP.ABSTRACT"
const VC = "VC.BUSINESS_TARGETS_MODEL.EDITOR"

function draft(overrides: Record<string, unknown> = {}) {
  return {
    draft_id: "d1",
    field_id: ABSTRACT,
    field_name: "Abstract",
    status: "needs_review",
    current_version: {
      draft_version_id: "v1",
      text: "Abstract über Förderfähigkeit.",
      character_count: 30,
      created_by: "user",
      created_at: "2026-07-01T09:30:00Z",
      content_hash: "h",
    },
    character_count: 30,
    character_limit: 300,
    open_issue_count: 0,
    evidence_links: [],
    open_issues: [],
    ...overrides,
  }
}

function reviewPkg(findings: Record<string, unknown>[] = []) {
  return {
    run_id: "r1",
    requirements: [],
    fields: [],
    findings,
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

function finding(overrides: Record<string, unknown> = {}) {
  return {
    finding_id: "f1",
    profile_id: "p",
    field_id: ABSTRACT,
    requirement_id: null,
    severity: "warning",
    description: "Bitte konkretisieren.",
    suggested_improvement: null,
    status: "open",
    advisory: true,
    ...overrides,
  }
}

function assessment(overrides: Record<string, unknown> = {}) {
  return {
    assessment_id: "a1",
    requirement_id: "REQ.PARTNER.CH",
    title: "Schweizer Wertschöpfung",
    status: "partial",
    basis: "deterministic_rule",
    reasoning: "Teilweise belegt.",
    stale: false,
    evidence_links: [
      {
        evidence_link_id: "el1",
        anchor_id: "an1",
        target_type: "requirement_assessment",
        target_id: "a1",
        status: "active",
        created_at: new Date().toISOString(),
      },
    ],
    open_issues: [],
    ...overrides,
  }
}

function mock(opts: {
  fields?: Record<string, unknown>[]
  findings?: Record<string, unknown>[]
  requirements?: Record<string, unknown>[]
} = {}) {
  server.use(
    http.get("/api/runs/r1/fields", () => HttpResponse.json(opts.fields ?? [draft()])),
    http.get("/api/runs/r1/evidence", () => HttpResponse.json([])),
    http.get("/api/runs/r1/requirements", () =>
      HttpResponse.json(opts.requirements ?? [])
    ),
    http.get("/api/runs/r1/review", () =>
      HttpResponse.json(reviewPkg(opts.findings ?? []))
    )
  )
}

afterEach(() => {
  setBackendMode("mock")
  window.sessionStorage.clear()
})

describe("Fehlende Angaben tab (per-field join)", () => {
  it("lists requirements joined via finding requirement_id with status + evidence", async () => {
    mock({
      findings: [finding({ requirement_id: "REQ.PARTNER.CH" })],
      requirements: [assessment()],
    })
    render(<LiveEditor runId="r1" />)
    await screen.findByLabelText("Entwurf Abstract")
    fireEvent.click(screen.getByRole("tab", { name: "Fehlende Angaben" }))

    expect(await screen.findByText("Schweizer Wertschöpfung")).toBeInTheDocument()
    expect(screen.getByText("Teilweise erfüllt")).toBeInTheDocument()
    expect(screen.getByText("Beleg vorhanden")).toBeInTheDocument()
    expect(screen.getByText("In Anforderungen öffnen")).toBeInTheDocument()
  })

  it("shows the explanatory empty state with a next action", async () => {
    mock({ requirements: [assessment()] }) // no finding links it to this field
    render(<LiveEditor runId="r1" />)
    await screen.findByLabelText("Entwurf Abstract")
    fireEvent.click(screen.getByRole("tab", { name: "Fehlende Angaben" }))

    expect(
      await screen.findByText(/Keine Anforderungen mit diesem Feld verknüpft/)
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Anforderungen prüfen" })
    ).toBeInTheDocument()
  })

  it("zeigt Platzhalter als konkrete Fragen mit Sprung-Aktion (R6)", async () => {
    mock({
      fields: [
        draft({
          current_version: {
            draft_version_id: "v1",
            text: "Teiltext [[Angabe ergänzen: Marktgrösse]] weiter.",
            character_count: 48,
            created_by: "user",
            created_at: "2026-07-01T09:30:00Z",
            content_hash: "h",
          },
        }),
      ],
    })
    render(<LiveEditor runId="r1" />)
    await screen.findByLabelText("Entwurf Abstract")
    fireEvent.click(screen.getByRole("tab", { name: "Fehlende Angaben" }))

    expect(
      await screen.findByText(/Welche Angabe gehört hier hin\?/)
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Im Text markieren" })
    ).toBeInTheDocument()
  })
})

describe("Versionen tab (current version card)", () => {
  it("shows the current version with origin, timestamp and beta note", async () => {
    mock()
    render(<LiveEditor runId="r1" />)
    await screen.findByLabelText("Entwurf Abstract")
    fireEvent.click(screen.getByRole("tab", { name: "Versionen" }))

    // Provenance appears twice since Slice 2: as the editor badge and in the
    // version card — assert presence, not uniqueness.
    expect((await screen.findAllByText("Manuell bearbeitet")).length).toBeGreaterThan(0)
    expect(screen.getByText("Aktuell")).toBeInTheDocument()
    expect(screen.getByText(/Gespeichert am/)).toBeInTheDocument()
    expect(
      screen.getByText("Versionshistorie ist in dieser Beta noch nicht verfügbar.")
    ).toBeInTheDocument()
  })
})

describe("Kommentar-Typ (visible prefix, no contract change)", () => {
  it("stores the chosen type as a text prefix and renders it as a badge", async () => {
    const posted: string[] = []
    mock({
      findings: [
        finding({
          finding_id: "f-q",
          description: "[Frage] Ist der Umsetzungspartner bestätigt?",
        }),
      ],
    })
    server.use(
      http.post("/api/runs/r1/human-decisions", async ({ request }) => {
        const body = (await request.json()) as { comment?: string }
        if (body.comment) posted.push(body.comment)
        return HttpResponse.json(
          {
            decision_id: "dec1",
            run_id: "r1",
            target_type: "portal_field_draft",
            target_id: "d1",
            action: "request_changes",
            user_id: "u1",
            created_at: new Date().toISOString(),
          },
          { status: 201 }
        )
      })
    )
    render(<LiveEditor runId="r1" />)
    await screen.findByLabelText("Entwurf Abstract")
    // Findings öffnen jetzt standardmässig „Schwächen“ — der Kommentarfluss
    // lebt im nachgeordneten Kommentare-Tab.
    fireEvent.click(screen.getByRole("tab", { name: "Kommentare" }))

    // Stored prefix renders as a badge; the text is shown without the prefix.
    // (Scoped to the finding row — "Frage" also exists as a type chip below.)
    const findingText = await screen.findByText("Ist der Umsetzungspartner bestätigt?")
    const findingRow = findingText.closest("li")
    expect(findingRow).not.toBeNull()
    expect(within(findingRow as HTMLElement).getByText("Frage")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Änderung nötig" }))
    fireEvent.change(screen.getByLabelText("Kommentar zum Abschnitt"), {
      target: { value: "Budgetzahl prüfen." },
    })
    fireEvent.click(screen.getByRole("button", { name: "Kommentar hinzufügen" }))
    await waitFor(() =>
      expect(posted).toEqual(["[Änderung nötig] Budgetzahl prüfen."])
    )
  })
})

describe("Markt tab + comparison sheet", () => {
  it("hides the comparison when the capability is off", async () => {
    mock({ fields: [draft({ draft_id: "d-vc", field_id: VC, field_name: "Value Creation" })] })
    render(<LiveEditor runId="r1" />)
    await screen.findByLabelText("Entwurf Value Creation")
    fireEvent.click(screen.getByRole("tab", { name: "Markt & Wettbewerb" }))

    expect(await screen.findByText("Noch keine Marktanalyse vorhanden")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Marktvergleich öffnen" })).toBeNull()
  })

  it("opens the wide sheet and inserts a source-backed argument into the draft", async () => {
    setBackendMode("live")
    window.sessionStorage.setItem("rf_active_project_id", "p1")
    mock({ fields: [draft({ draft_id: "d-vc", field_id: VC, field_name: "Value Creation" })] })
    server.use(
      http.get("/api/capabilities", () =>
        HttpResponse.json({
          api_version: "1.1.0",
          polling_interval_seconds: 2,
          supported_source_types: ["pdf"],
          features: { market_comparison: true },
        })
      ),
      http.get("/api/projects/p1/market-comparisons/latest", () =>
        HttpResponse.json({
          comparison_id: "c1",
          project_id: "p1",
          status: "ready_for_review",
          comparison_version: 1,
          research_gaps: ["Marktgrösse Schweiz unbelegt"],
          warnings: [],
          item_count: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          items: [
            {
              item_id: "i1",
              name: "Acme Plattform",
              category: "competitor",
              description: null,
              target_customer_segment: "Industrie-KMU",
              offering_summary: null,
              strengths: "Etablierte Basis",
              weaknesses: "Keine Rezyklat-Verarbeitung",
              differentiation_relevance:
                "Verarbeitet Rezyklate bei niedrigerer Prozesstemperatur",
              relation_to_project: "competing",
              confidence_label: "source_backed",
              status: "proposed",
              source_document_ids: ["s1"],
              evidence_quotes: [
                {
                  quote: "Acme bietet keine Rezyklat-Linie an.",
                  source_document_id: "s1",
                  source_version_id: "sv1",
                },
              ],
            },
          ],
        })
      )
    )
    render(<LiveEditor runId="r1" />)
    const textarea = (await screen.findByLabelText(
      "Entwurf Value Creation"
    )) as HTMLTextAreaElement
    fireEvent.click(screen.getByRole("tab", { name: "Markt & Wettbewerb" }))

    const openButton = await screen.findByRole("button", {
      name: "Marktvergleich öffnen",
    })
    fireEvent.click(openButton)

    const sheet = await screen.findByTestId("market-comparison-sheet")
    expect(within(sheet).getByText("Acme Plattform")).toBeInTheDocument()
    fireEvent.click(
      within(sheet).getByRole("button", { name: "Als Argument übernehmen" })
    )

    await waitFor(() =>
      expect(textarea.value).toContain(
        "Abgrenzung zu Acme Plattform: Verarbeitet Rezyklate bei niedrigerer Prozesstemperatur."
      )
    )
    // Inserted, not saved: the editor is dirty and the sheet says so.
    expect(within(sheet).getByText(/noch nicht gespeichert/)).toBeInTheDocument()
    expect(screen.getByText("Änderungen")).toBeInTheDocument()
  })
})
