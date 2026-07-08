import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"

vi.mock(
  "@/components/editor/rich-text-editor",
  async () => await import("./mocks/rich-text-editor")
)

import { LiveEditor } from "@/components/editor/live-editor"

const SOL = "SOL.INNOVATION_SOLUTION.EDITOR"
const VC = "VC.BUSINESS_TARGETS_MODEL.EDITOR"

function vcDraft(overrides: Record<string, unknown> = {}) {
  return {
    draft_id: "d-vc",
    field_id: VC,
    field_name: "Value Creation",
    status: "draft",
    current_version: {
      draft_version_id: "v1", text: "3.1 ... 3.2 ...", character_count: 16,
      created_by: "template", created_at: new Date().toISOString(), content_hash: "h",
    },
    character_count: 16,
    character_limit: 15000,
    open_issue_count: 0,
    evidence_links: [],
    open_issues: [],
    ...overrides,
  }
}

function vcSuggestionResult() {
  return {
    suggestion_id: "s-vc", operation_id: "opvc", field_id: VC, base_version_id: "v1",
    suggested_text: "3.1 Wertschöpfung neu 3.2 Geschäftsmodell neu [Marktzahl fehlt]",
    rationale: "ok", evidence: [], open_issue_ids: [],
    placeholders: [{ label: "Marktzahl", reason: "fehlt" }],
    character_count: 60, character_limit: 15000, warnings: ["contains_placeholders"],
  }
}

function solDraft(overrides: Record<string, unknown> = {}) {
  return {
    draft_id: "d-sol",
    field_id: SOL,
    field_name: "Innovation Solution",
    status: "draft",
    current_version: {
      draft_version_id: "v1",
      text: "4.1 ... 4.2 ... 4.3 ... 4.4 ... 4.5 ...",
      character_count: 40,
      created_by: "template",
      created_at: new Date().toISOString(),
      content_hash: "h",
    },
    character_count: 40,
    character_limit: 25000,
    open_issue_count: 0,
    evidence_links: [],
    open_issues: [],
    ...overrides,
  }
}

function abstractDraft() {
  return { ...solDraft(), draft_id: "d-abs", field_id: "INTRO.APP.ABSTRACT", field_name: "Abstract" }
}

function reviewPkg() {
  return {
    run_id: "r1", requirements: [], fields: [], findings: [], approval_status: "blocked",
    blocker_count: 0, warning_count: 0, open_issues: [], review_package_version: "rpv",
    current_approval_scope_hash: "h".repeat(64), recheck_required: false, stale_finding_count: 0,
  }
}

function suggestionResult() {
  return {
    suggestion_id: "s1", operation_id: "op1", field_id: SOL, base_version_id: "v1",
    suggested_text: "4.1 neu 4.2 neu 4.3 neu 4.4 neu 4.5 neu",
    rationale: "ok", evidence: [], open_issue_ids: [], placeholders: [],
    character_count: 39, character_limit: 25000, warnings: [],
  }
}

// The A2 control lives in the KI-Vorschlag pane → switch to KI-Assist first
// (the pane is CSS-hidden in Bearbeiten; jsdom would find it anyway, but the
// test should follow the real user flow).
async function openKiAssist() {
  fireEvent.click(await screen.findByRole("button", { name: "KI-Assist" }))
}

async function clickGenerate() {
  await openKiAssist()
  // Scope to the A2 control inside the KI pane.
  const control = await screen.findByTestId("a2-suggestion-control")
  fireEvent.click(
    within(control).getByRole("button", { name: /KI-Vorschlag erstellen/ })
  )
}

function baseMock(fields: Record<string, unknown>[]) {
  server.use(
    http.get("/api/runs/r1/fields", () => HttpResponse.json(fields)),
    http.get("/api/runs/r1/evidence", () => HttpResponse.json([])),
    http.get("/api/runs/r1/requirements", () => HttpResponse.json([])),
    http.get("/api/runs/r1/review", () => HttpResponse.json(reviewPkg())),
    http.get(`/api/runs/r1/fields/${SOL}`, () => HttpResponse.json(solDraft())),
  )
}

describe("LiveEditor A2 suggestions", () => {
  it("shows the AI control only for Solution & Innovation", async () => {
    baseMock([abstractDraft()])
    render(<LiveEditor runId="r1" />)
    await screen.findByText("Abstract")
    await openKiAssist()
    // The default-selected field is the Abstract → no A2 control, but the
    // availability is explained with the approved reason + CTA (R4.2).
    expect(screen.queryByTestId("a2-suggestion-control")).not.toBeInTheDocument()
    const unavailable = screen.getByTestId("a2-field-unavailable")
    expect(unavailable).toHaveTextContent(
      "Für dieses Feld ist noch kein KI-Vorschlag verfügbar."
    )
    expect(
      within(unavailable).getByRole("button", { name: "Strukturvorlage nutzen" })
    ).toBeInTheDocument()
  })

  it("renders the empty-state hint for the SOL field", async () => {
    baseMock([solDraft()])
    render(<LiveEditor runId="r1" />)
    await openKiAssist()
    await screen.findByTestId("a2-suggestion-control")
    expect(
      screen.getByText("KI-Vorschlag für diesen Abschnitt noch nicht erstellt.")
    ).toBeInTheDocument()
  })

  it("generates a suggestion, shows side-by-side and accepts it", async () => {
    baseMock([solDraft()])
    server.use(
      http.post(`/api/runs/r1/fields/${SOL}/redrafts`, () =>
        HttpResponse.json({ operation_id: "op1" }, { status: 202 })
      ),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "redraft", resource_id: "d-sol",
          status: "succeeded", created_at: new Date().toISOString(), result: suggestionResult(),
        })
      ),
      http.patch(`/api/runs/r1/fields/${SOL}`, () =>
        HttpResponse.json(
          solDraft({
            current_version: {
              draft_version_id: "v2", text: "4.1 neu 4.2 neu 4.3 neu 4.4 neu 4.5 neu",
              character_count: 39, created_by: "agent", created_at: new Date().toISOString(),
              content_hash: "h2",
            },
          })
        )
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate()
    // Side-by-side dialog appears with the suggestion.
    await waitFor(() =>
      expect(screen.getByTestId("suggestion-text").textContent).toContain("4.5 neu")
    )
    fireEvent.click(screen.getByRole("button", { name: "Übernehmen" }))
    await waitFor(() =>
      expect(
        screen.getByText(/erneute Prüfung ist vor der Freigabe erforderlich/)
      ).toBeInTheDocument()
    )
  })

  it("renders side-by-side and accepts a Value Creation (VC) suggestion", async () => {
    server.use(
      http.get("/api/runs/r1/fields", () => HttpResponse.json([vcDraft()])),
      http.get("/api/runs/r1/evidence", () => HttpResponse.json([])),
      http.get("/api/runs/r1/requirements", () => HttpResponse.json([])),
      http.get("/api/runs/r1/review", () => HttpResponse.json(reviewPkg())),
      http.get(`/api/runs/r1/fields/${VC}`, () => HttpResponse.json(vcDraft())),
      http.post(`/api/runs/r1/fields/${VC}/redrafts`, () =>
        HttpResponse.json({ operation_id: "opvc" }, { status: 202 })
      ),
      http.get("/api/operations/opvc", () =>
        HttpResponse.json({
          operation_id: "opvc", resource_type: "redraft", resource_id: "d-vc",
          status: "succeeded", created_at: new Date().toISOString(),
          result: vcSuggestionResult(),
        })
      ),
      http.patch(`/api/runs/r1/fields/${VC}`, () =>
        HttpResponse.json(
          vcDraft({
            current_version: {
              draft_version_id: "v2",
              text: "3.1 Wertschöpfung neu 3.2 Geschäftsmodell neu [Marktzahl fehlt]",
              character_count: 60, created_by: "agent",
              created_at: new Date().toISOString(), content_hash: "h2",
            },
          })
        )
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate()
    await waitFor(() =>
      expect(screen.getByTestId("suggestion-text").textContent).toContain("3.2 Geschäftsmodell")
    )
    // Placeholder warning surfaces; no provider/model names anywhere.
    expect(screen.getByText(/Platzhalter/i)).toBeInTheDocument()
    expect(screen.queryByText(/anthropic|openai|gpt|claude|sonnet/i)).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "Übernehmen" }))
    await waitFor(() =>
      expect(
        screen.getByText(/erneute Prüfung ist vor der Freigabe erforderlich/)
      ).toBeInTheDocument()
    )
  })

  // R4.2 — je reason_code: freigegebener Text + CTA (Grund + Ausweg statt Generiksatz).
  it("503 without reason_code falls back to provider_unavailable (fail-closed)", async () => {
    baseMock([solDraft()])
    server.use(
      http.post(`/api/runs/r1/fields/${SOL}/redrafts`, () =>
        HttpResponse.json({ code: "ai_unavailable" }, { status: 503 })
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate()
    await waitFor(() =>
      expect(
        screen.getByText("Es ist kein freigegebener KI-Provider konfiguriert.")
      ).toBeInTheDocument()
    )
    expect(
      screen.getByRole("button", { name: "Provider-Konfiguration prüfen" })
    ).toBeInTheDocument()
  })

  const reasonCases: Array<{ code: string; text: string; cta: string }> = [
    {
      code: "nda_locked",
      text: "Für gesperrte/NDA-Daten sind KI-Vorschläge deaktiviert.",
      cta: "Verarbeitungsmodus prüfen",
    },
    {
      code: "mode_deterministic_only",
      text: "Dieses Projekt ist aktuell auf regelbasierte Verarbeitung beschränkt.",
      cta: "Verarbeitungsmodus ändern",
    },
    {
      code: "provider_unavailable",
      text: "Es ist kein freigegebener KI-Provider konfiguriert.",
      cta: "Provider-Konfiguration prüfen",
    },
    {
      code: "run_mode_mismatch",
      text: "Der aktuelle Analysemodus passt nicht zum Feldvorschlag.",
      cta: "Analysemodus prüfen",
    },
    {
      code: "missing_sources",
      text: "Für einen belastbaren Vorschlag fehlen passende Quellen.",
      cta: "Quelle hinzufügen",
    },
  ]

  for (const { code, text, cta } of reasonCases) {
    it(`503 with reason_code=${code} shows the approved text and CTA`, async () => {
      baseMock([solDraft()])
      server.use(
        http.post(`/api/runs/r1/fields/${SOL}/redrafts`, () =>
          HttpResponse.json(
            { code: "ai_unavailable", reason_code: code, detail: text },
            { status: 503 }
          )
        )
      )
      render(<LiveEditor runId="r1" />)
      await clickGenerate()
      await waitFor(() => expect(screen.getByText(text)).toBeInTheDocument())
      // CTA rendered as link (navigation) or button (disclosure/action).
      const control = screen.getByTestId("a2-suggestion-control")
      expect(
        within(control).getByRole(
          code === "provider_unavailable" ? "button" : "link",
          { name: cta }
        )
      ).toBeInTheDocument()
    })
  }

  it("provider_unavailable CTA discloses the admin hint", async () => {
    baseMock([solDraft()])
    server.use(
      http.post(`/api/runs/r1/fields/${SOL}/redrafts`, () =>
        HttpResponse.json(
          { code: "ai_unavailable", reason_code: "provider_unavailable" },
          { status: 503 }
        )
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate()
    const cta = await screen.findByRole("button", {
      name: "Provider-Konfiguration prüfen",
    })
    fireEvent.click(cta)
    expect(
      screen.getByText(/durch Ihre Administration konfiguriert/)
    ).toBeInTheDocument()
  })

  it("dismisses the suggestion without saving", async () => {
    baseMock([solDraft()])
    server.use(
      http.post(`/api/runs/r1/fields/${SOL}/redrafts`, () =>
        HttpResponse.json({ operation_id: "op1" }, { status: 202 })
      ),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "redraft", resource_id: "d-sol",
          status: "succeeded", created_at: new Date().toISOString(), result: suggestionResult(),
        })
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate()
    await screen.findByRole("button", { name: "Vorschlag ausblenden" })
    fireEvent.click(screen.getByRole("button", { name: "Vorschlag ausblenden" }))
    await waitFor(() =>
      expect(screen.queryByTestId("suggestion-text")).not.toBeInTheDocument()
    )
    // The empty-state hint returns; no recheck notice (nothing was saved).
    expect(
      screen.getByText("KI-Vorschlag für diesen Abschnitt noch nicht erstellt.")
    ).toBeInTheDocument()
  })
})
