import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import { LiveRunBanner } from "@/components/run/live-run-banner"

describe("LiveRunBanner", () => {
  it("benennt einen deterministischen aktiven Lauf ehrlich und bietet den Live-Lauf an", () => {
    const onCreate = vi.fn()
    render(
      <LiveRunBanner processingMode="deterministic_only" onCreate={onCreate} />
    )
    expect(
      screen.getByText("Der aktive Lauf verwendet nur regelbasierte Verarbeitung.")
    ).toBeInTheDocument()
    expect(
      screen.getByText(/bleibt unverändert als Auditspur/)
    ).toBeInTheDocument()
    const button = screen.getByRole("button", { name: "Neuen Live-Lauf erstellen" })
    expect(button).toBeEnabled()
    fireEvent.click(button)
    expect(onCreate).toHaveBeenCalledTimes(1)
  })

  it("benennt einen Demo-Cloud-Lauf als Nicht-Live-Lauf", () => {
    render(<LiveRunBanner processingMode="cloud_assisted" onCreate={() => {}} />)
    expect(
      screen.getByText("Der aktive Lauf verwendet keine Live-KI.")
    ).toBeInTheDocument()
  })

  it("deaktiviert die Aktion mit konkretem Grund — nie ein stiller Demo-Ersatz", () => {
    const onCreate = vi.fn()
    render(
      <LiveRunBanner
        processingMode="deterministic_only"
        disabledReason="Live-KI ist deaktiviert. Öffnen Sie den Systemstatus, um die Verbindung zu prüfen."
        onCreate={onCreate}
      />
    )
    const button = screen.getByRole("button", { name: "Neuen Live-Lauf erstellen" })
    expect(button).toBeDisabled()
    expect(
      screen.getByText(/Live-KI ist deaktiviert/)
    ).toBeInTheDocument()
    fireEvent.click(button)
    expect(onCreate).not.toHaveBeenCalled()
  })
})
