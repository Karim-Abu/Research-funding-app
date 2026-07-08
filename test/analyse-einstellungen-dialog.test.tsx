import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { AnalyseEinstellungenDialog } from "@/components/run/analyse-einstellungen-dialog"
import type { AnalyseSettings, DataClass } from "@/lib/types"

function renderDialog(dataClass: DataClass, onStart = vi.fn()) {
  render(
    <AnalyseEinstellungenDialog
      open
      onOpenChange={() => {}}
      role="member"
      dataClass={dataClass}
      onStart={onStart}
    />
  )
  return onStart
}

describe("AnalyseEinstellungenDialog — cloud-processing gate", () => {
  it("public: requires the cloud confirmation before starting a cloud run", () => {
    const onStart = renderDialog("public")
    // The cloud opt-in is on by default for public; the confirmation is required.
    expect(
      screen.getByText(/Cloud-KI kann für diesen Durchlauf bewusst freigegeben/)
    ).toBeInTheDocument()
    const start = screen.getByRole("button", { name: "Analyse starten" })
    expect(start).toBeDisabled()

    fireEvent.click(
      screen.getByLabelText("Cloud-KI für diesen Durchlauf erlauben")
    )
    expect(start).toBeEnabled()
    fireEvent.click(start)
    const settings = onStart.mock.calls[0][0] as AnalyseSettings
    expect(settings.ki).toBe(true)
    expect(settings.cloudConfirmed).toBe(true)
    expect(settings.web).toBe(false)
  })

  it("does not imply data stays local or that the provider never processes it", () => {
    renderDialog("public")
    const dialog = screen.getByText(
      /Cloud-KI kann ausgewählte Inhalte an den konfigurierten KI-Dienst übermitteln/
    )
    expect(dialog).toBeInTheDocument()
    expect(screen.queryByText(/bleibt lokal/i)).toBeNull()
    expect(screen.queryByText(/niemals verarbeitet/i)).toBeNull()
    expect(screen.queryByText(/Förderchancen/i)).toBeNull()
    // No provider/model identifiers surface.
    expect(screen.queryByText(/anthropic/i)).toBeNull()
    expect(screen.queryByText(/openai|gpt|claude/i)).toBeNull()
  })

  it("confidential: cloud is blocked and no confirmation is shown", () => {
    const onStart = renderDialog("confidential")
    expect(
      screen.queryByLabelText("Cloud-KI für diesen Durchlauf erlauben")
    ).toBeNull()
    expect(
      screen.getByText(/keine externen KI- oder Webdienste/)
    ).toBeInTheDocument()
    const start = screen.getByRole("button", { name: "Analyse starten" })
    expect(start).toBeEnabled() // a local-only run needs no confirmation
    fireEvent.click(start)
    const settings = onStart.mock.calls[0][0] as AnalyseSettings
    expect(settings.ki).toBe(false)
    expect(settings.cloudConfirmed).toBe(false)
  })

  // R4.1: NDA / gesperrt (D3) — wie confidential lokal-only, nie Cloud/Web.
  it("nda: cloud and web stay blocked, no confirmation is shown", () => {
    const onStart = renderDialog("nda")
    expect(
      screen.queryByLabelText("Cloud-KI für diesen Durchlauf erlauben")
    ).toBeNull()
    expect(
      screen.getByText(/keine externen KI- oder Webdienste/)
    ).toBeInTheDocument()
    const start = screen.getByRole("button", { name: "Analyse starten" })
    fireEvent.click(start)
    const settings = onStart.mock.calls[0][0] as AnalyseSettings
    expect(settings.ki).toBe(false)
    expect(settings.web).toBe(false)
    expect(settings.cloudConfirmed).toBe(false)
  })
})
