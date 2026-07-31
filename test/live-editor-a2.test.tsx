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
  afterEach(() => {
    setBackendMode("mock")
    window.sessionStorage.clear()
  })

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
    // A non-A2 field → no control; the hint explains honestly which fields are
    // supported. The former «Strukturvorlage nutzen»-CTA is gone (it only
    // focused the editor and suggested a nonexistent action — Katalog 2026-07-23).
    expect(screen.queryByTestId("a2-suggestion-control")).not.toBeInTheDocument()
    const unavailable = screen.getByTestId("a2-field-unavailable")
    expect(unavailable).toHaveTextContent(
      "Für dieses Feld ist noch kein Abschnittsvorschlag verfügbar."
    )
    expect(unavailable).toHaveTextContent(/Verfügbar für Abstract/)
    expect(within(unavailable).queryByRole("button")).not.toBeInTheDocument()
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

  // Erst-Entwurf — leeres/Platzhalter-Feld bekommt eine ehrliche Erst-Entwurf-
  // Aktion statt «Text mit KI verbessern» (Backend erzeugt jetzt auch dann
  // einen Vorschlag; siehe field_drafting_context._section_is_initial_draft).
  it("Erst-Entwurf: Platzhalter-Feld zeigt «Erst-Entwurf erstellen» mit Erklärsatz", async () => {
    setBackendMode("live")
    const text = "[[Angabe ergänzen: Abstract (wird in Aramis publiziert)]]"
    baseMock(
      [{
        ...abstractDraft(),
        current_version: {
          draft_version_id: "v1", text, character_count: text.length,
          created_by: "template", created_at: new Date().toISOString(),
          content_hash: "h",
        },
      }],
      { generation_mode: "real_eval" }
    )
    render(<LiveEditor runId="r1" />)
    await openKiAssist()
    const control = await screen.findByTestId("a2-suggestion-control")
    expect(
      await within(control).findByRole("button", { name: "Erst-Entwurf erstellen" })
    ).toBeEnabled()
    expect(within(control).getByTestId("a2-action-explainer")).toHaveTextContent(
      "Noch kein Text vorhanden"
    )
  })

  it("Erst-Entwurf: Platzhalter-Unterabschnitt zeigt die Erst-Entwurf-Aktion, echter Text nicht", async () => {
    setBackendMode("live")
    const text =
      "4.1 Eigener Text\n4.2\n[[Angabe ergänzen: Antwort fachlich ergänzen]]\n" +
      "4.3 Alt\n4.4 Alt\n4.5.1 Alt\n4.5.2 Alt\n4.5.3 Alt\n4.5.4 Alt\n4.6 Alt"
    baseMock(
      [
        solDraft({
          current_version: {
            draft_version_id: "v1", text, character_count: text.length,
            created_by: "template", created_at: new Date().toISOString(),
            content_hash: "h",
          },
        }),
      ],
      { generation_mode: "real_eval" }
    )
    render(<LiveEditor runId="r1" />)
    await openKiAssist()
    const control = await screen.findByTestId("a2-suggestion-control")
    fireEvent.change(
      within(control).getByLabelText("Zielabschnitt für Vorschlag"),
      { target: { value: "4.2" } }
    )
    expect(
      await within(control).findByRole("button", { name: "Erst-Entwurf erstellen" })
    ).toBeEnabled()
    // Abschnitt mit Anwendertext auf der Markerzeile bleibt beim Verbessern.
    fireEvent.change(
      within(control).getByLabelText("Zielabschnitt für Vorschlag"),
      { target: { value: "4.1" } }
    )
    expect(
      await within(control).findByRole("button", { name: "Text mit KI verbessern" })
    ).toBeEnabled()
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
        "KI-Vorschläge sind noch nicht verfügbar. Ein Lead-Admin kann die Verbindung im Systemstatus prüfen."
      )
    ).toBeInTheDocument()
    expect(
      within(control).getByRole("button", { name: "Vorschlag erstellen" })
    ).toBeDisabled()
    const cta = within(control).getByRole("link", {
      name: "Systemstatus öffnen",
    })
    expect(cta).toHaveAttribute("href", "/systemstatus")
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
          "Die letzte Verbindungsprüfung war nicht erfolgreich. Ein Lead-Admin kann die Verbindung im Systemstatus erneut prüfen."
        )
      ).toBeInTheDocument()
    )
    const control = screen.getByTestId("a2-suggestion-control")
    expect(
      within(control).getByRole("link", { name: "Systemstatus öffnen" })
    ).toHaveAttribute("href", "/systemstatus")
    expect(screen.queryByTestId("suggestion-review-sheet")).toBeNull()
    expect(screen.queryByText(/Demo/)).toBeNull()
  })

  // §4 Demo-Slice — Alternativroute nur nach transientem Providerfehler,
  // ausschliesslich auf expliziten Klick.
  it("transienter Providerfehler: «Mit alternativem Modell versuchen» sendet die Alternativroute", async () => {
    setBackendMode("live")
    baseMock([solDraft()], { generation_mode: "real_eval" })
    const bodies: Array<Record<string, unknown>> = []
    server.use(
      http.post(`/api/runs/r1/fields/${SOL}/redrafts`, async ({ request }) => {
        bodies.push((await request.json()) as Record<string, unknown>)
        return HttpResponse.json(
          { operation_id: `op${bodies.length}` },
          { status: 202 }
        )
      }),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "redraft", resource_id: "d-sol",
          status: "failed", created_at: new Date().toISOString(),
          error: {
            code: "agent_invocation_failed",
            detail: "Es konnte kein Vorschlag erstellt werden.",
            retry_with_alternative_model: true,
          },
        })
      ),
      http.get("/api/operations/op2", () =>
        HttpResponse.json({
          operation_id: "op2", resource_type: "redraft", resource_id: "d-sol",
          status: "succeeded", created_at: new Date().toISOString(),
          result: suggestionResult(),
        })
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate("4.2")
    expect(
      await screen.findByRole("button", { name: "Erneut versuchen" })
    ).toBeInTheDocument()
    fireEvent.click(
      screen.getByRole("button", { name: "Mit alternativem Modell versuchen" })
    )
    await screen.findByTestId("suggestion-review-sheet")
    expect(bodies[0].model_preference).toBeUndefined()
    expect(bodies[1].model_preference).toBe("alternative")
  })

  it("Aufruf-Limit erreicht: klare Meldung statt generischem Fehler", async () => {
    setBackendMode("live")
    baseMock([solDraft()], { generation_mode: "real_eval" })
    server.use(
      http.post(`/api/runs/r1/fields/${SOL}/redrafts`, () =>
        HttpResponse.json({ operation_id: "op1" }, { status: 202 })
      ),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "redraft", resource_id: "d-sol",
          status: "failed", created_at: new Date().toISOString(),
          error: {
            code: "cost_guard_blocked",
            status: 503,
            reason_code: "ai_call_limit_reached",
            detail:
              "Das Limit für KI-Aufrufe in diesem Analyse-Lauf ist erreicht.",
          },
        })
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate("4.2")
    expect(
      await screen.findByText(/Limit für KI-Aufrufe in diesem Analyse-Lauf/)
    ).toBeInTheDocument()
    expect(screen.queryByText("Der Vorschlag konnte nicht erstellt werden.")).toBeNull()
  })

  it("Fehler ohne Transient-Flag bietet keine Alternativroute an", async () => {
    setBackendMode("live")
    baseMock([solDraft()], { generation_mode: "real_eval" })
    server.use(
      http.post(`/api/runs/r1/fields/${SOL}/redrafts`, () =>
        HttpResponse.json({ operation_id: "op1" }, { status: 202 })
      ),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "redraft", resource_id: "d-sol",
          status: "failed", created_at: new Date().toISOString(),
          error: {
            code: "agent_invocation_failed",
            detail: "Es konnte kein Vorschlag erstellt werden.",
          },
        })
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate("4.2")
    expect(
      await screen.findByRole("button", { name: "Erneut versuchen" })
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Mit alternativem Modell versuchen" })
    ).toBeNull()
  })

  it("deterministischer Abschnittsfehler: Klartext mit Marker, kein «Erneut versuchen»", async () => {
    // Regression «section_marker_missing:4.5.2» (2026-07-24): der echte Grund
    // erscheint, und ein sinnloser Retry wird nicht angeboten.
    setBackendMode("live")
    baseMock([solDraft()], { generation_mode: "real_eval" })
    server.use(
      http.post(`/api/runs/r1/fields/${SOL}/redrafts`, () =>
        HttpResponse.json({ operation_id: "op1" }, { status: 202 })
      ),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "redraft", resource_id: "d-sol",
          status: "failed", created_at: new Date().toISOString(),
          error: {
            code: "section_marker_missing:4.5.2",
            status: 422,
            detail: "Die Markerzeile «4.5.2» fehlt im Text.",
          },
        })
      )
    )
    render(<LiveEditor runId="r1" />)
    await clickGenerate("4.2")
    expect(
      await screen.findByText(/Die Markerzeile «4.5.2» fehlt im Text/)
    ).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Erneut versuchen" })).toBeNull()
    expect(
      screen.queryByRole("button", { name: "Mit alternativem Modell versuchen" })
    ).toBeNull()
  })

  it("Zielabschnitt ohne Markerzeile ist im Dropdown deaktiviert", async () => {
    // Ziel-tolerantes Gating (2026-07-24): fehlende Marker sind sichtbar,
    // aber nicht wählbar — vorhandene Abschnitte bleiben bearbeitbar.
    setBackendMode("live")
    const text =
      "4.1 Alt\n4.2 Alt\n4.3 Alt\n4.4 Alt\n4.5.1 Alt\n4.5.3 Alt\n4.5.4 Alt\n4.6 Alt"
    baseMock(
      [
        solDraft({
          current_version: {
            draft_version_id: "v1", text, character_count: text.length,
            created_by: "template", created_at: new Date().toISOString(),
            content_hash: "h",
          },
        }),
      ],
      { generation_mode: "real_eval" }
    )
    render(<LiveEditor runId="r1" />)
    await openKiAssist()
    const control = await screen.findByTestId("a2-suggestion-control")
    expect(
      within(control).getByRole("option", { name: "4.5.2 — fehlt im Text" })
    ).toBeDisabled()
    expect(within(control).getByRole("option", { name: "4.2" })).toBeEnabled()
  })

  // §10 — Quellen-Redraft nur mit positiv geprüfter Live-Quelle.
  it("«Mit geprüften Quellen neu formulieren» erscheint nur mit positiv geprüfter Live-Quelle", async () => {
    setBackendMode("live")
    const { setActiveProjectId } = await import("@/lib/intake-store")
    setActiveProjectId("p1")
    baseMock([solDraft()], {
      generation_mode: "real_eval",
      features: { web_research: true },
    })
    server.use(
      http.get("/api/projects/p1/research-workspace", () =>
        HttpResponse.json({
          brief: {},
          queries: [],
          results: [{
            result_id: "res1", title: "Swiss health data report",
            source_url: "https://example.ch/report", domain: "example.ch",
            retrieved_at: new Date().toISOString(), relevance_reason: "passend",
            status: "imported", content_review_status: "reviewed",
            support_status: "supports", execution_mode: "live",
            source_locations: [],
          }],
          provider_mode: "live",
        })
      )
    )
    render(<LiveEditor runId="r1" />)
    await openKiAssist()
    expect(
      await screen.findByTestId("research-redraft-action")
    ).toHaveTextContent("Mit geprüften Quellen neu formulieren")
  })

  it("ohne geprüfte Live-Quelle gibt es keinen Quellen-Redraft-Button", async () => {
    setBackendMode("live")
    const { setActiveProjectId } = await import("@/lib/intake-store")
    setActiveProjectId("p1")
    baseMock([solDraft()], {
      generation_mode: "real_eval",
      features: { web_research: true },
    })
    server.use(
      http.get("/api/projects/p1/research-workspace", () =>
        HttpResponse.json({
          brief: {},
          queries: [],
          results: [{
            result_id: "res1", title: "Demo-Quelle",
            source_url: "https://research.example.org/x", domain: "example.org",
            retrieved_at: new Date().toISOString(), relevance_reason: "Demo",
            status: "imported", content_review_status: "reviewed",
            support_status: "supports", execution_mode: "fake_demo",
            source_locations: [],
          }],
          provider_mode: "fake_demo",
        })
      )
    )
    render(<LiveEditor runId="r1" />)
    await openKiAssist()
    await screen.findByTestId("a2-suggestion-control")
    expect(screen.queryByTestId("research-redraft-action")).toBeNull()
  })

  it("frischer Live-Vorschlag entfernt das Analyse-Herkunfts-Banner", async () => {
    // Regression: setA2FromRun(false) beim Erzeugen — ein neu erzeugter
    // Vorschlag darf nicht als «Vorschlag aus der Analyse» erscheinen.
    baseMock([solDraft()])
    server.use(
      http.get(`/api/runs/r1/fields/${SOL}/suggestion`, () =>
        HttpResponse.json({ suggestion: suggestionResult() })
      ),
      http.post(`/api/runs/r1/fields/${SOL}/redrafts`, () =>
        HttpResponse.json({ operation_id: "op1" }, { status: 202 })
      ),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "redraft", resource_id: "d-sol",
          status: "succeeded", created_at: new Date().toISOString(),
          result: suggestionResult(),
        })
      )
    )
    render(<LiveEditor runId="r1" />)
    await openKiAssist()
    expect(await screen.findByTestId("run-suggestion-hint")).toBeInTheDocument()
    await clickGenerate("4.2")
    await screen.findByTestId("suggestion-review-sheet")
    fireEvent.keyDown(document, { key: "Escape" })
    await waitFor(() =>
      expect(screen.queryByTestId("suggestion-review-sheet")).toBeNull()
    )
    expect(screen.queryByTestId("run-suggestion-hint")).toBeNull()
    // Der frische Vorschlag bleibt mit neutralem Prüfhinweis sichtbar.
    expect(screen.getByText("Prüfung erforderlich")).toBeInTheDocument()
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
    // Side-by-side dialog appears with the suggestion (v3: Inhalte leben in
    // der Block-Diff-Liste; suggestion-text ist der Spaltenkopf).
    await waitFor(() =>
      expect(screen.getByTestId("suggestion-diff").textContent).toContain("4.2 Neuheit neu")
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
      expect(screen.getByTestId("suggestion-diff").textContent).toContain("3.2 Geschäftsmodell")
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
    // Sheet zu, aber der Vorschlag ist über «Vorschlag prüfen» wieder da.
    const reopen = await screen.findByRole("button", { name: "Vorschlag prüfen" })
    fireEvent.click(reopen)
    expect(await screen.findByTestId("suggestion-text")).toBeInTheDocument()
  })
})
