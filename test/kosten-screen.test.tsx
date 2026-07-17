import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { KostenScreen } from "@/components/kosten/kosten-screen"
import { RUNS, SERVICES, USAGE_LIMITS } from "@/lib/kosten-mock-data"
import type { KostenRunViewModel } from "@/lib/kosten"

describe("KostenScreen", () => {
  it("rendert Kopf, KPI-Übersicht und Budgetinformationen", () => {
    render(<KostenScreen role="member" />)

    expect(screen.getByRole("heading", { level: 1, name: "Kosten & Laufzeit" })).toBeInTheDocument()
    expect(screen.getByText(/Budgetverbrauch, Durchlauf-Historie/)).toBeInTheDocument()
    expect(screen.getByText(/Struktur und Darstellung entsprechen/)).toBeInTheDocument()
    expect(screen.getByText("Projektverbrauch")).toBeInTheDocument()
    expect(screen.getByText("Ø Kosten pro Lauf")).toBeInTheDocument()
    expect(screen.getByText("Ø Laufzeit")).toBeInTheDocument()
    expect(screen.getByText("Höchster bekannter Betrag")).toBeInTheDocument()
    expect(screen.getAllByText(/mind\. CHF 4\.20/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Restbudget:/)).toBeInTheDocument()
    expect(screen.getByText(/höchstens CHF 15\.80/)).toBeInTheDocument()
  })

  it("zeigt Modell, Provider, Laufzeit, Kosten und alle Run-Status", () => {
    render(<KostenScreen role="member" />)
    const table = screen.getByRole("table", { name: "Durchlauf-Historie" })

    expect(within(table).getByRole("columnheader", { name: "Modell / Provider" })).toBeInTheDocument()
    expect(within(table).getByRole("columnheader", { name: "Laufzeit" })).toBeInTheDocument()
    expect(within(table).getByRole("columnheader", { name: "Kosten" })).toBeInTheDocument()
    expect(within(table).getAllByText(/Claude \+ OpenAI \+ Firecrawl/).length).toBeGreaterThan(0)
    expect(within(table).getAllByText("2 min 8 s").length).toBeGreaterThan(0)
    expect(within(table).getAllByText("Abgeschlossen").length).toBeGreaterThan(0)
    expect(within(table).getByText("Gestoppt: Kostenlimit")).toBeInTheDocument()
    expect(within(table).getByText("Fehlgeschlagen")).toBeInTheDocument()
    expect(within(table).getByText("Abgebrochen")).toBeInTheDocument()
  })

  it("öffnet den Drawer und zeigt Übersicht, Audit und Ausführungsaufschlüsselung", async () => {
    render(<KostenScreen role="member" />)
    const table = screen.getByRole("table", { name: "Durchlauf-Historie" })
    const runRow = within(table).getAllByRole("row", { name: /Details zu Analyse vom/ })[0]

    fireEvent.keyDown(runRow, { key: "Enter" })

    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText("Abgeschlossen")).toBeInTheDocument()
    expect(within(dialog).getByText("2 min 8 s")).toBeInTheDocument()
    expect(within(dialog).getAllByText("~ CHF 0.72").length).toBeGreaterThan(0)
    expect(within(dialog).getByText(/Claude \+ OpenAI \+ Firecrawl/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Audit-Referenz:/)).toBeInTheDocument()
    expect(within(dialog).getByText("AE-2031")).toBeInTheDocument()
    expect(within(dialog).getByText("Faktenanalyse")).toBeInTheDocument()
    expect(within(dialog).getByText("Textvorschläge")).toBeInTheDocument()
    expect(within(dialog).queryByText("Faktenanalyse v2")).toBeNull()

    fireEvent.click(within(dialog).getByRole("button", { name: "Technische Details" }))
    expect(await within(dialog).findByText(/Faktenanalyse v2/)).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })

  it("sucht und stellt Filter sowie Sortierung bereit", () => {
    render(<KostenScreen role="member" />)
    const search = screen.getByLabelText("Nach Nutzer:in oder Audit-Referenz suchen")

    fireEvent.change(search, { target: { value: "AE-2029" } })
    expect(screen.getByText(/1 Durchlauf/)).toBeInTheDocument()
    expect(screen.getAllByText("Abschnitt neu erstellt").length).toBeGreaterThan(0)
    expect(screen.getByRole("combobox", { name: "Status filtern" })).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: "Art filtern" })).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: "Provider oder Modell filtern" })).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: "Durchläufe sortieren" })).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Zurücksetzen" }))
    expect(screen.getAllByText(/8 Durchläufe/).length).toBeGreaterThan(0)
  })

  it("zeigt einen verständlichen Filter-Leerzustand", () => {
    render(<KostenScreen role="member" />)
    fireEvent.change(
      screen.getByLabelText("Nach Nutzer:in oder Audit-Referenz suchen"),
      { target: { value: "nicht vorhanden" } }
    )
    expect(screen.getByText("Keine passenden Durchläufe")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Filter zurücksetzen" })).toBeInTheDocument()
  })

  it("zeigt Provideraggregation ohne Qualitätsversprechen", () => {
    render(<KostenScreen role="member" />)
    expect(screen.getByRole("heading", { name: "Modelle & Provider" })).toBeInTheDocument()
    expect(screen.getByRole("table", { name: "Modell- und Provider-Nutzung" })).toBeInTheDocument()
    expect(screen.getAllByText("Technisch erfolgreich").length).toBeGreaterThan(0)
    expect(screen.getByText(/keine Bewertung der inhaltlichen Qualität/)).toBeInTheDocument()
  })

  it("beschränkt Dienste und Limitbearbeitung auf lead_admin", () => {
    const { rerender } = render(<KostenScreen role="member" />)
    expect(screen.queryByRole("heading", { name: "Dienste & Verbindung" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Beispiel-Limit pro Lauf bearbeiten" })).toBeNull()

    rerender(<KostenScreen role="lead_admin" />)
    expect(screen.getByRole("heading", { name: "Dienste & Verbindung" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Beispiel-Limit pro Lauf bearbeiten" })).toBeInTheDocument()
    const testButtons = screen.getAllByRole("button", { name: "Verbindung testen" })
    expect(testButtons).toHaveLength(SERVICES.length)
    for (const button of testButtons) expect(button).toBeDisabled()
    expect(screen.getAllByText("In der Beispielansicht nicht verfügbar.")).toHaveLength(SERVICES.length)
  })

  it("ändert das Beispiel-Limit nur lokal und validiert den Wertebereich", () => {
    render(<KostenScreen role="lead_admin" />)
    fireEvent.click(screen.getByRole("button", { name: "Beispiel-Limit pro Lauf bearbeiten" }))
    const input = screen.getByLabelText("Limit pro Lauf (CHF)")
    fireEvent.change(input, { target: { value: "6" } })
    fireEvent.click(screen.getByRole("button", { name: "Beispiel-Limit übernehmen" }))
    expect(screen.getByRole("alert")).toHaveTextContent("Zulässig")

    fireEvent.change(input, { target: { value: "3" } })
    fireEvent.click(screen.getByRole("button", { name: "Beispiel-Limit übernehmen" }))
    expect(screen.getByText("CHF 3.00")).toBeInTheDocument()
    expect(screen.getByText(/werden nicht gespeichert/)).toBeInTheDocument()
  })

  it("rendert leere und unvollständige Daten ohne erfundene Werte", async () => {
    const { rerender } = render(
      <KostenScreen role="member" runs={[]} services={[]} usage={USAGE_LIMITS} />
    )
    expect(screen.getByText("Noch keine Durchläufe")).toBeInTheDocument()
    expect(screen.getByText("Keine Modell- oder Providerdaten verfügbar.")).toBeInTheDocument()

    const incompleteRun: KostenRunViewModel = {
      id: "incomplete",
      startedAt: "2026-06-11T09:00:00+02:00",
      type: "analysis",
      user: "Mara Beispiel",
      status: "completed",
      kiEnabled: true,
      webEnabled: false,
      providerLabels: [],
      modelLabels: [],
      cost: { status: "unavailable" },
      executions: [],
    }
    rerender(<KostenScreen role="member" runs={[incompleteRun]} />)
    expect(screen.getAllByText("Nicht verfügbar").length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole("button", { name: /Details zu Analyse vom/ }))
    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText("Keine Audit-Referenz verfügbar.")).toBeInTheDocument()
    expect(within(dialog).getAllByText("Nicht verfügbar").length).toBeGreaterThan(0)
  })

  it("behält die übergebenen Beispielwerte unverändert", () => {
    render(<KostenScreen role="member" runs={RUNS} />)
    expect(RUNS[0].cost).toEqual({ status: "estimated", amountChf: 0.72 })
  })
})
