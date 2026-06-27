import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { PortalTransfer } from "@/components/portal-transfer/portal-transfer"
import type { PortalFieldDraftDto } from "@/lib/fields"
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
    await waitFor(() => expect(screen.getByText("Kopiert")).toBeInTheDocument())
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
    expect(
      screen.getByText("Dieser Feldtext enthält noch offene Angaben.")
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Text kopieren" }))
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
    expect(
      screen.getByText("Der Text überschreitet das Innolink-Zeichenlimit.")
    ).toBeInTheDocument()
    expect(screen.getByText("Die Review-Freigabe ist nicht aktuell.")).toBeInTheDocument()
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
      screen.getByText(/Review-Status ist in der Demo-Ansicht nicht verfügbar/)
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
