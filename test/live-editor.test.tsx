import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"

// Tiptap needs real DOM ranges jsdom lacks → swap the editor for a textarea
// stub (real editor covered by Playwright). Keeps value/selection assertions.
vi.mock(
  "@/components/editor/rich-text-editor",
  async () => await import("./mocks/rich-text-editor")
)

import { LiveEditor } from "@/components/editor/live-editor"

function draft(overrides: Record<string, unknown> = {}) {
  return {
    draft_id: "d1",
    field_id: "INTRO.APP.ABSTRACT",
    field_name: "Abstract",
    status: "needs_review",
    current_version: {
      draft_version_id: "v1",
      text: "[[Angabe ergänzen: Abstract über Förderfähigkeit]]",
      character_count: 50,
      created_by: "template",
      created_at: new Date().toISOString(),
      content_hash: "h",
    },
    character_count: 50,
    character_limit: 300,
    open_issue_count: 1,
    evidence_links: [],
    open_issues: [],
    ...overrides,
  }
}

function reviewPkg(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "r1",
    requirements: [],
    fields: [draft()],
    findings: [],
    approval_status: "blocked",
    blocker_count: 1,
    warning_count: 0,
    open_issues: [],
    review_package_version: "rpv-test",
    current_approval_scope_hash: "h".repeat(64),
    recheck_required: false,
    stale_finding_count: 0,
    ...overrides,
  }
}

function mock(opts: { patch?: () => Response; review?: () => Response } = {}) {
  server.use(
    http.get("/api/runs/r1/fields", () => HttpResponse.json([draft()])),
    http.get("/api/runs/r1/evidence", () => HttpResponse.json([])),
    http.get("/api/runs/r1/requirements", () => HttpResponse.json([])),
    // Kein offener Lauf-Vorschlag im Standardfall.
    http.get("/api/runs/r1/fields/:field/suggestion", () =>
      HttpResponse.json({ suggestion: null })
    ),
    http.get("/api/runs/r1/review", () =>
      opts.review ? opts.review() : HttpResponse.json(reviewPkg())
    ),
    http.post("/api/runs/r1/human-decisions", () =>
      HttpResponse.json(
        {
          target_type: "portal_field_draft",
          target_id: "d1",
          action: "request_changes",
          comment: "x",
          decision_id: "dec1",
          user_id: "u1",
          run_id: "r1",
          created_at: new Date().toISOString(),
        },
        { status: 201 }
      )
    ),
    http.get("/api/runs/r1/fields/INTRO.APP.ABSTRACT", () => HttpResponse.json(draft())),
    http.patch("/api/runs/r1/fields/INTRO.APP.ABSTRACT", () =>
      opts.patch ? opts.patch() : HttpResponse.json(draft())
    )
  )
}

describe("LiveEditor", () => {
  it("preselects the deep-linked field (?field=…) instead of the first one", async () => {
    const second = draft({
      draft_id: "d2",
      field_id: "SOL.INNOVATION_SOLUTION.EDITOR",
      field_name: "Innovation & Lösung",
      current_version: {
        draft_version_id: "v2",
        text: "Text der Lösung.",
        character_count: 16,
        created_by: "user",
        created_at: new Date().toISOString(),
        content_hash: "h2",
      },
    })
    server.use(
      http.get("/api/runs/r1/fields", () => HttpResponse.json([draft(), second])),
      http.get("/api/runs/r1/evidence", () => HttpResponse.json([])),
      http.get("/api/runs/r1/requirements", () => HttpResponse.json([])),
      http.get("/api/runs/r1/fields/:field/suggestion", () =>
        HttpResponse.json({ suggestion: null })
      ),
      http.get("/api/runs/r1/review", () => HttpResponse.json(reviewPkg()))
    )
    render(<LiveEditor runId="r1" initialFieldId="SOL.INNOVATION_SOLUTION.EDITOR" />)
    await waitFor(() =>
      expect(screen.getByDisplayValue("Text der Lösung.")).toBeInTheDocument()
    )
  })

  it("RUN 4B §2.1: zeigt die originale Portalfrage im Feldkopf", async () => {
    mock()
    server.use(
      http.get("/api/runs/r1/portal-fields", () =>
        HttpResponse.json([
          {
            field_id: "INTRO.APP.ABSTRACT",
            section: "INTRO",
            label:
              "Fassen Sie Ihr Innovationsvorhaben in wenigen Sätzen zusammen.",
            character_limit: 300,
            mandatory_status: "required",
            required: true,
            support_mode: "draft_text",
            field_kind: "single_editor",
            display_mode: "draft",
            draft_available: true,
            subsections: [],
          },
        ])
      )
    )
    render(<LiveEditor runId="r1" />)
    await screen.findByLabelText("Entwurf Abstract")
    expect(await screen.findByTestId("portal-question")).toHaveTextContent(
      "Portalfrage: Fassen Sie Ihr Innovationsvorhaben in wenigen Sätzen zusammen."
    )
  })

  it("renders the template draft with badge, hint and Unicode text", async () => {
    mock()
    render(<LiveEditor runId="r1" />)
    await waitFor(() =>
      expect(
        screen.getByDisplayValue(/Abstract über Förderfähigkeit/)
      ).toBeInTheDocument()
    )
    expect(screen.getByText("Strukturvorlage")).toBeInTheDocument()
    expect(screen.getByText("Bitte fachlich prüfen und ergänzen.")).toBeInTheDocument()
    expect(screen.getByText(/\/ 300 Zeichen/)).toBeInTheDocument()
    // No AI / redraft / human-check controls in live mode.
    expect(screen.queryByText(/Neu erstellen/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Geprüft von/)).not.toBeInTheDocument()
  })

  it("labels a carried-over version 'Übernommen aus vorherigem Durchlauf'", async () => {
    const carried = draft({
      current_version: {
        draft_version_id: "v9",
        text: "Kurzfassung aus dem vorherigen Durchlauf.",
        character_count: 41,
        created_by: "carried_over",
        created_at: new Date().toISOString(),
        content_hash: "h9",
      },
      open_issue_count: 0,
    })
    server.use(
      http.get("/api/runs/r1/fields", () => HttpResponse.json([carried])),
      http.get("/api/runs/r1/evidence", () => HttpResponse.json([])),
      http.get("/api/runs/r1/requirements", () => HttpResponse.json([])),
      http.get("/api/runs/r1/fields/:field/suggestion", () =>
        HttpResponse.json({ suggestion: null })
      ),
      http.get("/api/runs/r1/review", () => HttpResponse.json(reviewPkg()))
    )
    render(<LiveEditor runId="r1" />)
    await waitFor(() =>
      expect(
        screen.getByDisplayValue("Kurzfassung aus dem vorherigen Durchlauf.")
      ).toBeInTheDocument()
    )
    expect(
      screen.getByText("Übernommen aus vorherigem Durchlauf")
    ).toBeInTheDocument()
    expect(screen.queryByText("Strukturvorlage")).not.toBeInTheDocument()
  })

  it("preserves local text and shows the conflict dialog on 409", async () => {
    mock({ patch: () => HttpResponse.json({ code: "stale_base_version" }, { status: 409 }) })
    render(<LiveEditor runId="r1" />)
    const textarea = await screen.findByLabelText("Entwurf Abstract")
    fireEvent.change(textarea, { target: { value: "Meine Änderung mit ä ö ü." } })
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }))
    await waitFor(() =>
      expect(
        screen.getByText("Dieser Abschnitt wurde zwischenzeitlich geändert.")
      ).toBeInTheDocument()
    )
    // Local text is NOT overwritten.
    expect((textarea as HTMLTextAreaElement).value).toBe("Meine Änderung mit ä ö ü.")
  })

  it("shows requirements for a field WITHOUT findings via affected_field_ids (Slice 4)", async () => {
    mock()
    server.use(
      http.get("/api/runs/r1/requirements", () =>
        HttpResponse.json([
          {
            assessment_id: "as1",
            requirement_id: "REQ.INNO.X",
            title: "Umsetzungspartner mit Schweiz-Bezug",
            status: "partial",
            basis: "hybrid",
            reasoning: "r",
            stale: false,
            evidence_links: [],
            open_issues: [],
            affected_field_ids: ["INTRO.APP.ABSTRACT"],
          },
        ])
      )
    )
    render(<LiveEditor runId="r1" />)
    fireEvent.click(await screen.findByRole("tab", { name: "Fehlende Angaben" }))
    await waitFor(() =>
      expect(
        screen.getByText("Umsetzungspartner mit Schweiz-Bezug")
      ).toBeInTheDocument()
    )
  })

  it("shows field findings and posts a section comment", async () => {
    mock({
      review: () =>
        HttpResponse.json(
          reviewPkg({
            findings: [
              {
                finding_id: "f1",
                profile_id: "p",
                field_id: "INTRO.APP.ABSTRACT",
                requirement_id: null,
                severity: "warning",
                description: "Bitte konkretisieren.",
                suggested_improvement: null,
                status: "open",
                advisory: true,
              },
            ],
          })
        ),
    })
    render(<LiveEditor runId="r1" />)
    // Findings öffnen standardmässig „Schwächen“ (Warum + nächste Aktion) …
    await waitFor(() =>
      expect(screen.getByText("Bitte konkretisieren.")).toBeInTheDocument()
    )
    // … der Kommentarfluss lebt im nachgeordneten Kommentare-Tab.
    fireEvent.click(screen.getByRole("tab", { name: "Kommentare" }))
    const comment = screen.getByLabelText("Kommentar zum Abschnitt")
    fireEvent.change(comment, { target: { value: "Neuer Kommentar." } })
    fireEvent.click(screen.getByRole("button", { name: "Kommentar hinzufügen" }))
    await waitFor(() =>
      expect((comment as HTMLTextAreaElement).value).toBe("")
    )
  })

  it("approves the selected section (field scope)", async () => {
    mock()
    server.use(
      http.post("/api/runs/r1/approvals", () =>
        HttpResponse.json(
          {
            approval_id: "ap1",
            run_id: "r1",
            scope: "field",
            status: "approved",
            approval_scope_hash: "h".repeat(64),
            approved_by: "u",
            created_at: new Date().toISOString(),
          },
          { status: 201 }
        )
      )
    )
    render(<LiveEditor runId="r1" />)
    // Freigabe lebt im Kommentare-Tab (Default ist jetzt „Schwächen“).
    fireEvent.click(await screen.findByRole("tab", { name: "Kommentare" }))
    const approve = await screen.findByRole("button", { name: "Abschnitt freigeben" })
    fireEvent.click(approve)
    await waitFor(() =>
      expect(screen.getByText("Abschnitt freigegeben.")).toBeInTheDocument()
    )
  })

  it("zeigt den im Analyse-Lauf erzeugten Vorschlag zur Prüfung an und übernimmt ihn nur explizit", async () => {
    let patched: Record<string, unknown> | null = null
    mock()
    server.use(
      http.get("/api/runs/r1/fields/INTRO.APP.ABSTRACT/suggestion", () =>
        HttpResponse.json({
          suggestion: {
            suggestion_id: "sg-run-1",
            operation_id: "op-run-1",
            field_id: "INTRO.APP.ABSTRACT",
            base_version_id: "v1",
            suggested_text: "Vorschlagstext aus dem Analyse-Lauf.",
            rationale: "An Belege angepasst.",
            evidence: [],
            open_issue_ids: [],
            placeholders: [],
            character_count: 36,
            character_limit: 300,
            warnings: [],
            ai_proposal: {
              suggestion_text: "Vorschlagstext aus dem Analyse-Lauf.",
              used_anchor_ids: [],
              missing_inputs: [],
              profile_id: "A2.introduction_public_summary",
              prompt_version: "v2",
              context_hash: "h",
              model_ref: "m",
              created_at: new Date().toISOString(),
              data_mode: "fake_test",
              provider: "fake",
              model: "m",
              human_review_required: true,
            },
          },
        })
      ),
      http.patch(
        "/api/runs/r1/fields/INTRO.APP.ABSTRACT",
        async ({ request }) => {
          patched = (await request.json()) as Record<string, unknown>
          return HttpResponse.json(
            draft({
              current_version: {
                draft_version_id: "v2",
                text: "Vorschlagstext aus dem Analyse-Lauf.",
                character_count: 36,
                created_by: "agent",
                created_at: new Date().toISOString(),
                content_hash: "h2",
              },
            })
          )
        }
      )
    )
    render(<LiveEditor runId="r1" />)
    // Hinweis erscheint, ohne dass der Text verändert wurde (nie Auto-Apply).
    expect(await screen.findByTestId("run-suggestion-hint")).toHaveTextContent(
      "Vorschlag aus der Analyse — Prüfung nötig."
    )
    expect(
      screen.getByDisplayValue(/Abstract über Förderfähigkeit/)
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Vorschlag prüfen" }))
    fireEvent.click(await screen.findByRole("button", { name: "Übernehmen" }))
    await waitFor(() => expect(patched).not.toBeNull())
    // Annahme läuft über den unveränderten updateField-Pfad.
    expect(patched!.source_operation_id).toBe("op-run-1")
    expect(patched!.text).toBe("Vorschlagstext aus dem Analyse-Lauf.")
  })

  it("saves a new version and shows the recheck notice", async () => {
    mock({
      patch: () =>
        HttpResponse.json(
          draft({
            current_version: {
              draft_version_id: "v2",
              text: "Gespeicherter Text.",
              character_count: 19,
              created_by: "user",
              created_at: new Date().toISOString(),
              content_hash: "h2",
            },
          })
        ),
    })
    render(<LiveEditor runId="r1" />)
    const textarea = await screen.findByLabelText("Entwurf Abstract")
    fireEvent.change(textarea, { target: { value: "Gespeicherter Text." } })
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }))
    await waitFor(() =>
      expect(screen.getByText(/erneute Prüfung ist vor der Freigabe erforderlich/)).toBeInTheDocument()
    )
  })
})
