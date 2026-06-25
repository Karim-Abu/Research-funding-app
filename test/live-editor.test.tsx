import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
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
    await waitFor(() =>
      expect(screen.getByText("Bitte konkretisieren.")).toBeInTheDocument()
    )
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
    const approve = await screen.findByRole("button", { name: "Abschnitt freigeben" })
    fireEvent.click(approve)
    await waitFor(() =>
      expect(screen.getByText("Abschnitt freigegeben.")).toBeInTheDocument()
    )
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
