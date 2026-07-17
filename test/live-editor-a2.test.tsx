import { afterEach, describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"

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
      draft_version_id: "v1", text: "3.1 Alt A\n3.2 Alt B\n3.3 Alt C", character_count: 29,
      created_by: "template", created_at: new Date().toISOString(), content_hash: "h",
    },
    character_count: 29,
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
    target_section: "3.2", generation_kind: "fake_demo",
    suggested_text: "3.2 Geschäftsmodell neu [Marktzahl fehlt]",
    rationale: "ok", evidence: [], open_issue_ids: [],
    placeholders: [{ label: "Marktzahl", reason: "fehlt" }],
    character_count: 44, character_limit: 15000, warnings: ["contains_placeholders"],
    section_result: {
      field_id: VC, target_section: "3.2",
      suggested_text: "3.2 Geschäftsmodell neu [Marktzahl fehlt]", rationale: "ok",
      preserved_facts: [], removed_or_reframed_claims: [], new_claims: [],
      missing_inputs: [{ label: "Marktzahl", reason: "fehlt" }],
      evidence_anchor_ids: [], open_issue_ids: [],
    },
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
      text: "4.1 Alt\n4.2 Alt\n4.3 Alt\n4.4 Alt\n4.5.1 Alt\n4.5.2 Alt\n4.5.3 Alt\n4.5.4 Alt\n4.6 Alt",
      character_count: 75,
      created_by: "template",
      created_at: new Date().toISOString(),
      content_hash: "h",
    },
    character_count: 75,
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

function unsupportedDraft() {
  return { ...solDraft(), draft_id: "d-name", field_id: "INTRO.APP.NAME", field_name: "Projekttitel" }
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
    target_section: "4.2", generation_kind: "fake_demo",
    suggested_text: "4.2 Neuheit neu",
    rationale: "ok", evidence: [], open_issue_ids: [], placeholders: [],
    character_count: 15, character_limit: 25000, warnings: [],
    section_result: {
      field_id: SOL, target_section: "4.2", suggested_text: "4.2 Neuheit neu",
      rationale: "ok", preserved_facts: ["Projektbegriff"],
      removed_or_reframed_claims: [], new_claims: [], missing_inputs: [],
      evidence_anchor_ids: [], open_issue_ids: [],
    },
  }
}

// The A2 control lives in the proposal pane → switch to Vorschläge first
// (the pane is CSS-hidden in Bearbeiten; jsdom would find it anyway, but the
// test should follow the real user flow).
async function openKiAssist() {
  fireEvent.click(await screen.findByRole("button", { name: "Vorschläge" }))
}

async function clickGenerate(targetSection?: string) {
  await openKiAssist()
  // Scope to the A2 control inside the proposal pane.
  const control = await screen.findByTestId("a2-suggestion-control")
  if (targetSection) {
    fireEvent.change(within(control).getByLabelText("Zielabschnitt für Vorschlag"), {
      target: { value: targetSection },
    })
  }
  fireEvent.click(
    within(control).getByRole("button", {
      name: /Vorschlag erstellen|Text mit KI verbessern/,
    })
  )
}

function baseMock(
  fields: Record<string, unknown>[],
  capabilities: Record<string, unknown> = { generation_mode: "fake_demo" }
) {
  server.use(
    http.get("/api/capabilities", () => HttpResponse.json({
      api_version: "1.1.0", polling_interval_seconds: 2,
      supported_source_types: ["txt"], features: {}, ...capabilities,
    })),
    http.get("/api/runs/r1/fields", () => HttpResponse.json(fields)),
    http.get("/api/runs/r1/evidence", () => HttpResponse.json([])),
    http.get("/api/runs/r1/requirements", () => HttpResponse.json([])),
    http.get("/api/runs/r1/review", () => HttpResponse.json(reviewPkg())),
    http.get("/api/runs/r1/fields/:fieldId/suggestion", () =>
      HttpResponse.json({ detail: "not found" }, { status: 404 })
    ),
    http.get("/api/runs/r1/portal-fields", () => HttpResponse.json([
      {
        field_id: SOL, section: "SOL", label: "Solution", character_limit: 25000,
        mandatory_status: "required", support_mode: "draft", field_kind: "composite",
        display_mode: "editor", draft_available: true,
        subsections: ["4.1", "4.2", "4.3", "4.4", "4.5.1", "4.5.2", "4.5.3", "4.5.4", "4.6"]
          .map((marker) => ({ marker, label: marker })),
      },
      {
        field_id: VC, section: "VC", label: "Value Creation", character_limit: 15000,
        mandatory_status: "required", support_mode: "draft", field_kind: "composite",
        display_mode: "editor", draft_available: true,
        subsections: ["3.1", "3.2", "3.3"].map((marker) => ({ marker, label: marker })),
      },
    ])),
    http.get(`/api/runs/r1/fields/${SOL}`, () => HttpResponse.json(solDraft())),
  )
}

describe("LiveEditor A2 suggestions", () => {
  // Einzelne Tests schalten für echte Capabilities-Antworten auf «live».
  afterEach(() => setBackendMode("mock"))

  it("shows the proposal control for the Abstract field (R5.5)", async () => {
    baseMock([abstractDraft()])
    render(<LiveEditor runId="r1" />)
    await screen.findByText("Abstract")
    await openKiAssist()
    // Abstract is now an A2-enabled field → the proposal control appears.
    expect(await screen.findByTestId("a2-suggestion-control")).toBeInTheDocument()
    expect(screen.queryByTestId("a2-field-unavailable")).not.toBeInTheDocument()
  })

  it("hides the proposal control for an unsupported field", async () => {
    baseMock([unsupportedDraft()])
    render(<LiveEditor runId="r1" />)
    await screen.findByText("Projekttitel")
    await openKiAssist()
    // A non-A2 field → no control, but the availability is explained with the
    // approved reason + CTA (R4.2).
    expect(screen.queryByTestId("a2-suggestion-control")).not.toBeInTheDocument()
    const unavailable = screen.getByTestId("a2-field-unavailable")
    expect(unavailable).toHaveTextContent(
      "Für dieses Feld ist noch kein Abschnittsvorschlag verfügbar."
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
      screen.getByText("Demo-Vorschlag (kein echtes KI-Modell) für diesen Abschnitt noch nicht erstellt.")
    ).toBeInTheDocument()
  })

  // Anf. 1/2 — modusabhängige Primäraktion + Erklärsatz direkt darüber.
  it("real_eval: Aktion «Text mit KI verbessern» mit Erklärsatz", async () => {
    setBackendMode("live")
    baseMock([solDraft()], { generation_mode: "real_eval" })
    render(<LiveEditor runId="r1" />)
    await openKiAssist()
    const control = await screen.findByTestId("a2-suggestion-control")
    expect(
      await within(control).findByRole("button", { name: "Text mit KI verbessern" })
    ).toBeEnabled()
    expect(within(control).getByTestId("a2-action-explainer")).toHaveTextContent(
      "Der ausgewählte Abschnitt wird neu strukturiert"
    )
    expect(
      screen.getByText("Live-KI-Vorschlag für diesen Abschnitt noch nicht erstellt.")
    ).toBeInTheDocument()
    expect(screen.queryByText(/Demo-Vorschlag/)).toBeNull()
  })

  it("ohne Provider: Aktion deaktiviert mit konkretem Grund und CTA", async () => {
    setBackendMode("live")
    baseMock([solDraft()], {
      generation_mode: "live_unavailable",
      generation_unavailable_reason: "live_preflight_required",
    })
    render(<LiveEditor runId="r1" />)
    await openKiAssist()
    const control = await screen.findByTestId("a2-suggestion-control")
    expect(
      await within(control).findByText(
        "Live-KI ist noch nicht freigegeben. Starten Sie im Live-Systemstatus den synthetischen Preflight."
      )
    ).toBeInTheDocument()
    expect(
      within(control).getByRole("button", { name: "Vorschlag erstellen" })
    ).toBeDisabled()
    const cta = within(control).getByRole("link", {
      name: "Live-Systemstatus prüfen",
    })
    expect(cta).toHaveAttribute("href", "/admin")
    // Kein stiller Demo-Ersatz und kein irreführender Leerzustand.
    expect(screen.queryByText(/Demo-Vorschlag/)).toBeNull()
    expect(screen.queryByText(/noch nicht erstellt/)).toBeNull()
  })

  // Anf. 6 — ein Live-Fehler erzeugt keinen Demo-Vorschlag.
  it("Live-Fehler zeigt Grund + Live-CTA und keinen Demo-Inhalt", async () => {
    setBackendMode("live")
    baseMock([solDraft()], { generation_mode: "real_eval" })
    server.use(
      http.post(`/api/runs/r1/fields/${SOL}/redrafts`, () =>
        HttpResponse.json(
          { code: "ai_unavailable", reason_code: "live_preflight_failed" },
          { status: 503 }
        )
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate("4.2")
    await waitFor(() =>
      expect(
        screen.getByText(
          "Der Live-Preflight ist fehlgeschlagen. Prüfen Sie den konkreten Routenfehler im Live-Systemstatus und wiederholen Sie den Test."
        )
      ).toBeInTheDocument()
    )
    const control = screen.getByTestId("a2-suggestion-control")
    expect(
      within(control).getByRole("link", { name: "Routenfehler prüfen" })
    ).toHaveAttribute("href", "/admin")
    expect(screen.queryByTestId("suggestion-review-sheet")).toBeNull()
    expect(screen.queryByText(/Demo/)).toBeNull()
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
              draft_version_id: "v2",
              text: "4.1 Alt\n4.2 Neuheit neu\n4.3 Alt\n4.4 Alt\n4.5.1 Alt\n4.5.2 Alt\n4.5.3 Alt\n4.5.4 Alt\n4.6 Alt",
              character_count: 83, created_by: "agent", generation_kind: "fake_demo",
              created_at: new Date().toISOString(),
              content_hash: "h2",
            },
          })
        )
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate("4.2")
    // Side-by-side dialog appears with the suggestion.
    await waitFor(() =>
      expect(screen.getByTestId("suggestion-text").textContent).toContain("4.2 Neuheit neu")
    )
    fireEvent.click(screen.getByRole("button", { name: "Übernehmen" }))
    await waitFor(() =>
      expect(
        screen.getByText(/Text übernommen – Qualitätsprüfung erneut erforderlich/)
      ).toBeInTheDocument()
    )
    // C8 — klarer Status nach der Übernahme (Badge, nicht nur Banner).
    expect(
      screen.getByText("In Bearbeitung – erneute Prüfung nötig")
    ).toBeInTheDocument()
  })

  it("renders side-by-side and accepts a Value Creation (VC) suggestion", async () => {
    baseMock([vcDraft()])
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
              text: "3.1 Alt A\n3.2 Geschäftsmodell neu [Marktzahl fehlt]\n3.3 Alt C",
              character_count: 62, created_by: "agent", generation_kind: "fake_demo",
              created_at: new Date().toISOString(), content_hash: "h2",
            },
          })
        )
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate("3.2")
    await waitFor(() =>
      expect(screen.getByTestId("suggestion-text").textContent).toContain("3.2 Geschäftsmodell")
    )
    // Placeholder warning surfaces; no provider/model names anywhere.
    expect(screen.getByText(/Platzhalter/i)).toBeInTheDocument()
    expect(screen.queryByText(/anthropic|openai|gpt|claude|sonnet/i)).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "Übernehmen" }))
    await waitFor(() =>
      expect(
        screen.getByText(/Text übernommen – Qualitätsprüfung erneut erforderlich/)
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
    await clickGenerate("4.2")
    await waitFor(() =>
      expect(
        screen.getByText("Für diese Datenklasse ist aktuell kein freigegebener KI-Provider konfiguriert. Die App führt nur regelbasierte Prüfungen aus.")
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
      text: "Für diese Datenklasse ist aktuell kein freigegebener KI-Provider konfiguriert. Die App führt nur regelbasierte Prüfungen aus.",
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
      await clickGenerate("4.2")
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
    await clickGenerate("4.2")
    const cta = await screen.findByRole("button", {
      name: "Provider-Konfiguration prüfen",
    })
    fireEvent.click(cta)
    expect(
      screen.getByText(/durch Ihre Administration konfiguriert/)
    ).toBeInTheDocument()
  })

  it("persistiert die Ablehnung als HumanDecision (C4) — ohne den Text zu ändern", async () => {
    baseMock([solDraft()])
    const decisions: Array<Record<string, unknown>> = []
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
      http.post("/api/runs/r1/human-decisions", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>
        decisions.push(body)
        return HttpResponse.json(
          {
            ...body, decision_id: "dec1", user_id: "u1", run_id: "r1",
            created_at: new Date().toISOString(),
          },
          { status: 201 }
        )
      })
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate("4.2")
    await screen.findByRole("button", { name: "Vorschlag ablehnen" })
    fireEvent.click(screen.getByRole("button", { name: "Vorschlag ablehnen" }))
    fireEvent.click(screen.getByRole("button", { name: "Eigene Formulierung bevorzugt" }))
    fireEvent.click(screen.getByRole("button", { name: "Ablehnen bestätigen" }))
    await waitFor(() =>
      expect(screen.queryByTestId("suggestion-text")).not.toBeInTheDocument()
    )
    // Serverseitig persistiert: target draft_suggestion + Grund; kein PATCH.
    await waitFor(() => expect(decisions).toHaveLength(1))
    expect(decisions[0]).toMatchObject({
      target_type: "draft_suggestion",
      target_id: "s1",
      action: "reject",
      comment: "Eigene Formulierung bevorzugt",
    })
    // The empty-state hint returns; no recheck notice (nothing was saved).
    expect(
      screen.getByText("Demo-Vorschlag (kein echtes KI-Modell) für diesen Abschnitt noch nicht erstellt.")
    ).toBeInTheDocument()
  })

  it("Schliessen (X) ist kein Verwerfen — der Vorschlag bleibt erreichbar", async () => {
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
    await clickGenerate("4.2")
    await screen.findByTestId("suggestion-review-sheet")
    fireEvent.click(screen.getByRole("button", { name: "Close" }))
    // Sheet zu, aber der Vorschlag ist über «Vorschlag anzeigen» wieder da.
    const reopen = await screen.findByRole("button", { name: "Vorschlag anzeigen" })
    fireEvent.click(reopen)
    expect(await screen.findByTestId("suggestion-text")).toBeInTheDocument()
  })
})
