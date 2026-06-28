import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { SuggestionReviewDialog } from "@/components/editor/suggestion-review-dialog"
import type { A2Suggestion } from "@/lib/redraft"

function suggestion(overrides: Partial<A2Suggestion> = {}): A2Suggestion {
  return {
    suggestion_id: "s1",
    operation_id: "op1",
    field_id: "SOL.INNOVATION_SOLUTION.EDITOR",
    base_version_id: "v1",
    suggested_text: "4.1 ... 4.2 ... 4.3 ... 4.4 ... 4.5 verbessert.",
    rationale: "An Belege angepasst.",
    evidence: [
      {
        anchor_id: "a1",
        quote: "Belegte Passage.",
        source_name: "Quelle.txt",
        verification_status: "exact_verified",
      },
    ],
    open_issue_ids: ["issue-1"],
    placeholders: [{ label: "Marktzahl", reason: "fehlt" }],
    character_count: 46,
    character_limit: 25000,
    warnings: ["contains_placeholders", "based_on_unconfirmed_facts"],
    ...overrides,
  }
}

describe("SuggestionReviewDialog", () => {
  it("renders side-by-side, evidence, char count and warnings", () => {
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="Aktueller Entwurf."
        suggestion={suggestion()}
        onAccept={() => {}}
        onDismiss={() => {}}
      />
    )
    expect(screen.getByTestId("current-text").textContent).toContain("Aktueller Entwurf.")
    expect(screen.getByTestId("suggestion-text").textContent).toContain("4.5 verbessert.")
    expect(screen.getByTestId("character-count").textContent).toContain("46 / 25000")
    expect(screen.getByText("Quelle.txt")).toBeInTheDocument()
    expect(screen.getByText("Belegte Passage.")).toBeInTheDocument()
    expect(screen.getByTestId("warning-contains_placeholders")).toBeInTheDocument()
    expect(screen.getByTestId("warning-based_on_unconfirmed_facts")).toBeInTheDocument()
    expect(screen.getByTestId("open-issues").textContent).toContain("1")
  })

  it("calls onAccept and onDismiss", () => {
    const onAccept = vi.fn()
    const onDismiss = vi.fn()
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion()}
        onAccept={onAccept}
        onDismiss={onDismiss}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: "Übernehmen" }))
    expect(onAccept).toHaveBeenCalledOnce()
    fireEvent.click(screen.getByRole("button", { name: "Vorschlag ausblenden" }))
    expect(onDismiss).toHaveBeenCalledOnce()
  })

  it("disables accept when over the character limit", () => {
    const onAccept = vi.fn()
    render(
      <SuggestionReviewDialog
        open
        onOpenChange={() => {}}
        currentText="x"
        suggestion={suggestion({ character_count: 26000 })}
        onAccept={onAccept}
        onDismiss={() => {}}
      />
    )
    const accept = screen.getByRole("button", { name: "Übernehmen" })
    expect(accept).toBeDisabled()
  })
})
