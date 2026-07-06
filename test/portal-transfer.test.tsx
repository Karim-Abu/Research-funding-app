import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { PortalTransfer } from "@/components/portal-transfer/portal-transfer"
import type { PortalFieldDraftDto } from "@/lib/fields"
import type { PortalFieldInfoDto } from "@/lib/portal-fields"
import type { ReviewPackageDto } from "@/lib/review"

function setClipboard(value: unknown) {
  Object.defineProperty(navigator, "clipboard", { value, configurable: true })
}
afterEach(() => setClipboard(undefined))

function field(
  fieldId: string,
  fieldName: string,
  text: string,
  overrides: Partial<PortalFieldDraftDto> = {}
): PortalFieldDraftDto {
  const count = [...text].length
  return {
    draft_id: fieldId,
    field_id: fieldId,
    field_name: fieldName,
    status: "needs_review",
    current_version: {
      draft_version_id: `${fieldId}-v`,
      text,
      character_count: count,
      created_by: "user",
      created_at: new Date("2026-06-25T10:00:00Z").toISOString(),
      content_hash: "h",
    },
    character_count: count,
    character_limit: 300,
    open_issue_count: 0,
    evidence_links: [],
    open_issues: [],
    ...overrides,
  }
}

function reviewPkg(overrides: Partial<ReviewPackageDto> = {}): ReviewPackageDto {
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
    ...overrides,
  }
}

describe("PortalTransfer", () => {
  it("toggle shows all portal sections incl. SUM; default shows only supported (Slice 4)", () => {
    const catalog: PortalFieldInfoDto[] = [
      {
        field_id: "INTRO.APP.ABSTRACT",
        section: "INTRO",
        label: "Abstract",
        character_limit: 300,
        mandatory_status: "required",
        required: true,
        support_mode: "draft_text",
        field_kind: "narrative_text",
        display_mode: "draft",
        draft_available: true,
      },
      {
        field_id: "INTRO.APP.EXECUTIVE_SUMMARY",
        section: "INTRO",
        label: "Executive Summary",
        character_limit: null,
        mandatory_status: "needs_verification",
        required: null,
        support_mode: "draft_text",
        field_kind: "narrative_text",
        display_mode: "draft",
        draft_available: false,
      },
      {
        field_id: "PS.WORK_PACKAGE.NAME",
        section: "PS",
        label: "Work package name",
        character_limit: null,
        mandatory_status: "required",
        required: true,
        support_mode: "user_input_or_suggestion",
        field_kind: "text_or_structured_input",
        display_mode: "checklist",
        draft_available: false,
      },
      {
        field_id: "SUM.COVER_LETTER.UPLOAD",
        section: "SUM",
        label: "Cover letter",
        character_limit: null,
        mandatory_status: "optional",
        required: false,
        support_mode: "upload_validate",
        field_kind: "file_upload",
        display_mode: "upload",
        draft_available: false,
      },
      {
        field_id: "SUM.SUBMIT.BUTTON",
        section: "SUM",
        label: "Submit application",
        character_limit: null,
        mandatory_status: "not_applicable",
        required: false,
        support_mode: "action_only",
        field_kind: "action_or_lookup",
        display_mode: "external_only",
        draft_available: false,
      },
    ]
    const fields = [field("INTRO.APP.ABSTRACT", "Abstract", "Kurzfassung.")]
    render(
      <PortalTransfer fields={fields} review={reviewPkg()} portalFields={catalog} />
    )

    // Default: supported view only — no manual checklist, no SUM section.
    expect(
      screen.queryByRole("heading", { name: "Im Portal manuell erfassen" })
    ).toBeNull()
    expect(screen.queryByText("Summary & Submit")).toBeNull()

    fireEvent.click(screen.getByRole("button", { name: "Alle Portalfelder" }))
    expect(
      screen.getByRole("heading", { name: "Im Portal manuell erfassen" })
    ).toBeInTheDocument()
    expect(screen.getByText("Summary & Submit")).toBeInTheDocument()
    // display_mode badges use user-facing labels, never technical values.
    expect(screen.getByText("Datei-Upload im Portal")).toBeInTheDocument()
    expect(screen.getByText("Im Portal beachten")).toBeInTheDocument()
    expect(
      screen.getByText("Textfeld im Portal — im MVP noch nicht unterstützt")
    ).toBeInTheDocument()
    expect(screen.queryByText("external_only")).toBeNull()
    // Supported draft field does NOT appear in the manual checklist.
    const checklist = screen.getByLabelText("Im Portal manuell erfassen")
    expect(checklist).not.toHaveTextContent("Abstract")
    // Read-only: no check-off inputs.
    expect(screen.queryByRole("checkbox")).toBeNull()

    // Back to the default view.
    fireEvent.click(screen.getByRole("button", { name: "Unterstützte Felder" }))
    expect(
      screen.queryByRole("heading", { name: "Im Portal manuell erfassen" })
    ).toBeNull()
  })

  it("groups fields by section in registry order and lists coverage", () => {
    const fields = [
      field("INTRO.APP.ABSTRACT", "Abstract", "Kurzfassung."),
      field("VC.BUSINESS_TARGETS_MODEL.EDITOR", "Value creation", "VC Text."),
      field("SOL.INNOVATION_SOLUTION.EDITOR", "Solution", "SOL Text."),
    ]
    render(<PortalTransfer fields={fields} review={reviewPkg()} />)
    const headings = screen
      .getAllByRole("heading", { level: 2 })
      .map((h) => h.textContent)
    expect(headings).toEqual(
      expect.arrayContaining(["Einleitung", "Wertschöpfung", "Lösung & Innovation"])
    )
    // Section order preserved (Einleitung before Wertschöpfung).
    expect(headings.indexOf("Einleitung")).toBeLessThan(headings.indexOf("Wertschöpfung"))
    // Coverage panel always present with the unsupported areas.
    expect(screen.getByText(/Arbeitspakete \(Work Packages\)/)).toBeInTheDocument()
    expect(
      screen.getByText(/müssen weiterhin direkt in\s+Innolink erfasst werden/)
    ).toBeInTheDocument()
  })

  it("keeps plain copy primary; formatted copy sits behind 'Erweitert' (M10.2)", async () => {
    // Formatted copy is only offered when ClipboardItem exists.
    setClipboard({ writeText: vi.fn(), write: vi.fn() })
    ;(globalThis as Record<string, unknown>).ClipboardItem = class {}
    try {
      const fields = [field("INTRO.APP.ABSTRACT", "Abstract", "Text.")]
      render(<PortalTransfer fields={fields} review={reviewPkg()} />)
      expect(screen.getByRole("button", { name: "Text kopieren" })).toBeInTheDocument()
      // Hidden until the user opens the advanced disclosure.
      expect(
        screen.queryByRole("button", { name: /Formatiert kopieren/ })
      ).toBeNull()
      fireEvent.click(screen.getByRole("button", { name: "Erweitert" }))
      expect(
        screen.getByRole("button", { name: /Formatiert kopieren \(experimentell\)/ })
      ).toBeInTheDocument()
    } finally {
      delete (globalThis as Record<string, unknown>).ClipboardItem
    }
  })

  it("plain copy puts ONLY the field text on the clipboard (no metadata)", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setClipboard({ writeText })
    const fields = [field("INTRO.APP.ABSTRACT", "Abstract", "Reiner Feldtext üöä.")]
    render(<PortalTransfer fields={fields} review={reviewPkg()} />)
    fireEvent.click(screen.getByRole("button", { name: "Text kopieren" }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("Reiner Feldtext üöä."))
    // Nothing else (field id, label, section, counts) leaked into the copy.
    const copied = writeText.mock.calls[0][0]
    expect(copied).toBe("Reiner Feldtext üöä.")
    // Session-only copy state with timestamp (M10.2 / F8).
    await waitFor(() => expect(screen.getByText(/Kopiert am/)).toBeInTheDocument())
  })

  it("shows a visible placeholder warning and confirms before copying", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setClipboard({ writeText })
    const fields = [
      field(
        "INTRO.APP.ABSTRACT",
        "Abstract",
        "Teiltext [[Angabe ergänzen: Rest]]",
        { open_issue_count: 1 }
      ),
    ]
    render(<PortalTransfer fields={fields} review={reviewPkg()} />)
    // Shared warning banner + compact per-card badge (M10.2 / F4).
    expect(
      screen.getByText(/1 Feld enthält noch offene Angaben/)
    ).toBeInTheDocument()
    expect(screen.getByText("Offene Angaben")).toBeInTheDocument()
    // Open fields lead back into the draft; copying needs a deliberate step.
    expect(
      screen.getByRole("button", { name: "Im Entwurf bearbeiten" })
    ).toHaveAttribute("href", "/editor?field=INTRO.APP.ABSTRACT")
    expect(screen.queryByRole("button", { name: "Text kopieren" })).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "Trotzdem kopieren…" }))
    // Confirmation appears; copy not yet performed.
    const confirm = await screen.findByRole("button", { name: "Trotzdem kopieren" })
    expect(writeText).not.toHaveBeenCalled()
    fireEvent.click(confirm)
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith("Teiltext [[Angabe ergänzen: Rest]]")
    )
  })

  it("warns on character-limit overflow and stale/missing review approval", () => {
    const fields = [
      field("INTRO.APP.ABSTRACT", "Abstract", "x".repeat(40), { character_limit: 10 }),
    ]
    render(
      <PortalTransfer fields={fields} review={reviewPkg({ approval_status: "stale" })} />
    )
    // Aggregated once in the shared banner …
    expect(
      screen.getByText(/1 Feld überschreitet das Innolink-Zeichenlimit/)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Prüfungs-Freigabe ist nicht aktuell \(betrifft 1 Feld\)/)
    ).toBeInTheDocument()
    // … and flagged compactly on the card.
    expect(screen.getByText("Zeichenlimit überschritten")).toBeInTheDocument()
    expect(screen.getByText("Prüfung nicht aktuell")).toBeInTheDocument()
  })

  it("renders the empty state when no copyable drafts exist", () => {
    render(<PortalTransfer fields={[]} review={reviewPkg()} />)
    expect(
      screen.getByText("Für diesen Lauf liegen noch keine übernehmbaren Feldtexte vor.")
    ).toBeInTheDocument()
    // Coverage panel still rendered.
    expect(screen.getByText(/Budget- und Finanzierungsplan/)).toBeInTheDocument()
  })

  it("shows the demo note in mock mode and never a portal-submission status", () => {
    const fields = [field("INTRO.APP.ABSTRACT", "Abstract", "Text.")]
    const { container } = render(
      <PortalTransfer fields={fields} review={null} mockMode />
    )
    expect(
      screen.getByText(/Prüfungs-Status ist in der Demo-Ansicht nicht verfügbar/)
    ).toBeInTheDocument()
    const text = container.textContent ?? ""
    // No false submission claim. ("nichts … eingereicht" is the correct disclaimer.)
    expect(text).not.toMatch(/einreichbereit|submitted_to_portal/i)
  })

  it("always shows the generic clipboard privacy reminder", () => {
    render(<PortalTransfer fields={[field("INTRO.APP.NAME", "Name", "x")]} review={null} />)
    expect(
      screen.getByText(/können dort von anderen lokalen Anwendungen gelesen werden/)
    ).toBeInTheDocument()
  })
})
