import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { CompletedAnalysisBanner } from "@/components/quellen/analysis-progress-banner"

describe("CompletedAnalysisBanner", () => {
  it("shows neutral copy without dummy counts", () => {
    const { container } = render(
      <CompletedAnalysisBanner
        onGoToRequirements={vi.fn()}
        onShowEvidence={vi.fn()}
      />
    )
    expect(
      screen.getByText(
        "Analyse abgeschlossen. Öffnen Sie Anforderungen und Evidenz für die Ergebnisse."
      )
    ).toBeInTheDocument()
    expect(screen.queryByText(/Dummy/)).not.toBeInTheDocument()
    expect(screen.queryByText(/12 Belege/)).not.toBeInTheDocument()
    expect(screen.queryByText(/19 Anforderungen/)).not.toBeInTheDocument()
    // Stricter guard: the banner must not contain any digits at all.
    expect(container.textContent).not.toMatch(/\d/)
    expect(
      screen.getByRole("button", { name: "Zu den Anforderungen" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Belege ansehen" })
    ).toBeInTheDocument()
  })
})
