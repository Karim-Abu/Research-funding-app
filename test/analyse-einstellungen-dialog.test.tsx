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

  // R4.3 (Owner-Entscheid 2026-07-08): intern/vertraulich = KI nur nach
  // manuellem Opt-in + verstandener Warnung, über den lokalen Pfad.
  it("confidential: default off — without opt-in the run stays rule-based", () => {
    const onStart = renderDialog("confidential")
    // Kein Cloud-Panel; die Warnung erscheint erst nach dem Einschalten.
    expect(
      screen.queryByLabelText("Cloud-KI für diesen Durchlauf erlauben")
    ).toBeNull()
    expect(screen.queryByTestId("local-ai-warning")).toBeNull()
    const start = screen.getByRole("button", { name: "Analyse starten" })
    expect(start).toBeEnabled() // ein regelbasierter Lauf braucht keine Freigabe
    fireEvent.click(start)
    const settings = onStart.mock.calls[0][0] as AnalyseSettings
    expect(settings.ki).toBe(false)
    expect(settings.cloudConfirmed).toBe(false)
  })

  for (const dc of ["internal", "confidential"] as const) {
    it(`${dc}: opt-in shows the warning and requires the acknowledgement`, () => {
      const onStart = renderDialog(dc)
      // KI einschalten → deutliche Warnung + Verstanden-Bestätigung.
      fireEvent.click(screen.getByRole("switch", { name: /KI-Unterstützung/ }))
      const warning = screen.getByTestId("local-ai-warning")
      expect(warning).toHaveTextContent(/Warnung: KI-Unterstützung/)
      expect(warning).toHaveTextContent(/lokalen Verarbeitungspfad/)
      expect(warning).toHaveTextContent(/nicht an externe KI-Dienste/)
      const start = screen.getByRole("button", { name: "Analyse starten" })
      expect(start).toBeDisabled() // ohne Verstanden-Bestätigung kein Start

      fireEvent.click(
        screen.getByLabelText("KI-Unterstützung für diesen Durchlauf freigeben")
      )
      expect(start).toBeEnabled()
      fireEvent.click(start)
      const settings = onStart.mock.calls[0][0] as AnalyseSettings
      expect(settings.ki).toBe(true)
      expect(settings.cloudConfirmed).toBe(true)
      expect(settings.web).toBe(false) // Webrecherche bleibt aus
    })
  }

  // R4.1/R4.3: NDA / gesperrt (D3) — KI-Schalter bleibt deaktiviert, kein Opt-in.
  it("nda: AI stays fully blocked — no toggle, no warning panel", () => {
    const onStart = renderDialog("nda")
    expect(
      screen.getByText(/Für NDA-geschützte oder gesperrte Inhalte/)
    ).toBeInTheDocument()
    // KI- UND Web-Schalter sind als "nicht verfügbar" markiert; Klick wirkungslos.
    expect(screen.getAllByText("Dienst aktuell nicht verfügbar")).toHaveLength(2)
    fireEvent.click(screen.getByRole("switch", { name: /KI-Unterstützung/ }))
    expect(screen.queryByTestId("local-ai-warning")).toBeNull()
    const start = screen.getByRole("button", { name: "Analyse starten" })
    fireEvent.click(start)
    const settings = onStart.mock.calls[0][0] as AnalyseSettings
    expect(settings.ki).toBe(false)
    expect(settings.web).toBe(false)
    expect(settings.cloudConfirmed).toBe(false)
  })
})
