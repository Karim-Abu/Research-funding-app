import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, within } from "@testing-library/react"
import { KiTeamScreen } from "@/components/ki-team/ki-team-page"
import {
  kiTeamRoles,
  kiTeamTexts,
  phaseAssignments,
  getKiTeamPhases,
} from "@/lib/ki-team-data"

// ---------------------------------------------------------------------------
// Katalog-Integrität
// ---------------------------------------------------------------------------

describe("KI-Team Rollenkatalog", () => {
  it("enthält exakt 10 eindeutige Rollen", () => {
    const ids = new Set(kiTeamRoles.map((r) => r.id))
    expect(ids.size).toBe(10)
    expect(kiTeamRoles).toHaveLength(10)
  })

  it("referenziert im Phasenband nur existierende Rollen", () => {
    const ids = new Set(kiTeamRoles.map((r) => r.id))
    for (const assignment of phaseAssignments) {
      for (const roleId of assignment.roleIds) {
        expect(ids.has(roleId), `Unbekannte Rolle: ${roleId}`).toBe(true)
      }
    }
  })

  it("ordnet alle Phasen echten Workflow-Schritten zu", () => {
    const phases = getKiTeamPhases()
    expect(phases).toHaveLength(8)
    // Jede Rolle erscheint in mindestens einer Phase.
    const usedIds = new Set(phases.flatMap((p) => p.roles.map((r) => r.id)))
    expect(usedIds.size).toBe(10)
  })
})

// ---------------------------------------------------------------------------
// Wording-Guards: keine positiven Autonomie- oder Erfolgsversprechen
// ---------------------------------------------------------------------------

function collectStrings(value: unknown): string[] {
  if (typeof value === "string") return [value]
  if (Array.isArray(value)) return value.flatMap(collectStrings)
  if (value && typeof value === "object") {
    return Object.values(value).flatMap(collectStrings)
  }
  return []
}

describe("KI-Team Wording", () => {
  const corpus = [...collectStrings(kiTeamRoles), ...collectStrings(kiTeamTexts)]

  it("enthält keine verbotenen Autonomie- oder Erfolgsbegriffe", () => {
    const forbidden = [
      /autonom/i,
      /vollautomatisch/i,
      /Erfolgschance/i,
      /Bewilligungswahrscheinlichkeit/i,
      /bewertet Ihre Chancen/i,
    ]
    for (const text of corpus) {
      for (const pattern of forbidden) {
        expect(text).not.toMatch(pattern)
      }
    }
  })

  it("verwendet «entscheidet» nur in Negationen", () => {
    for (const text of corpus) {
      if (/entscheidet/i.test(text)) {
        expect(
          /entscheidet nicht|nie entscheidet/i.test(text),
          `Nicht verneinte Verwendung von «entscheidet»: ${text}`
        ).toBe(true)
      }
    }
  })

  it("verwendet «Förderwahrscheinlichkeit» nur verneint oder in der Nie-Liste", () => {
    const nieListe = new Set<string>(kiTeamTexts.nieEntscheidet.punkte)
    for (const text of corpus) {
      if (/Förderwahrscheinlichkeit/i.test(text)) {
        const erlaubt =
          /keine Aussage zur Förderwahrscheinlichkeit/i.test(text) ||
          nieListe.has(text)
        expect(erlaubt, `Riskante Verwendung: ${text}`).toBe(true)
      }
    }
  })
})

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("KiTeamScreen", () => {
  it("rendert Header, Intro und Pflichttexte", () => {
    render(<KiTeamScreen />)
    expect(screen.getByRole("heading", { name: "KI-Team" })).toBeInTheDocument()
    expect(
      screen.getByText(
        "Wer hier arbeitet, was automatisch läuft — und wo Sie entscheiden."
      )
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        "Die App kombiniert KI-Vorschläge mit festen Prüfregeln. Sie sehen, welche Rolle wo unterstützt und welche Punkte Sie selbst freigeben."
      )
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        "Ablaufsteuerung: Ein festes Programm steuert die Reihenfolge der Schritte — keine KI."
      )
    ).toBeInTheDocument()
    expect(screen.getByText("Was die KI hier nie entscheidet")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Die App reicht keinen Antrag ein und macht keine Aussage zur Förderwahrscheinlichkeit."
      )
    ).toBeInTheDocument()
  })

  it("zeigt alle 10 Rollen als kompakte Chips im Phasenband", () => {
    render(<KiTeamScreen />)
    const buttons = screen.getAllByRole("button")
    for (const role of kiTeamRoles) {
      // Rollen können mehrfach erscheinen (mehrere Phasen, Desktop + Mobile).
      expect(
        buttons.some((button) => button.textContent?.includes(role.name))
      ).toBe(true)
    }
  })

  it("öffnet den Detail-Drawer per Klick auf eine Rollenkarte", async () => {
    render(<KiTeamScreen />)
    const card = screen.getAllByRole("button", {
      name: /Fakten-Leser \(A1\)/,
    })[0]
    fireEvent.click(card)
    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText("Aufgabe")).toBeInTheDocument()
    expect(within(dialog).getByText("Letzter Lauf")).toBeInTheDocument()
    expect(within(dialog).getByText("Noch kein Lauf")).toBeInTheDocument()
    expect(card).toHaveAttribute("aria-expanded", "true")
  })

  it("zeigt Provider- und Datenzeilen nicht in der Hauptfläche", async () => {
    render(<KiTeamScreen />)
    expect(
      screen.queryAllByText(/Kontrollierter KI-Dienst \(Demo\)/)
    ).toHaveLength(0)
    fireEvent.click(screen.getByRole("button", { name: "Details" }))
    expect(
      screen.queryAllByText(/Kontrollierter KI-Dienst \(Demo\)/)
    ).toHaveLength(0)
    expect(screen.queryByText(/Daten: Ihre/)).not.toBeInTheDocument()

    const chip = screen.getAllByRole("button", {
      name: /Fakten-Leser \(A1\)/,
    })[0]
    fireEvent.click(chip)
    const dialog = await screen.findByRole("dialog")
    expect(
      within(dialog).getByText(/Kontrollierter KI-Dienst \(Demo\)/)
    ).toBeInTheDocument()
    expect(within(dialog).getByText("Technische Details")).toBeInTheDocument()
  })

  it("zeigt konkrete Schutzregeln statt generischem Datenschutztext", () => {
    render(<KiTeamScreen />)
    expect(screen.getByText("Keine automatische Einreichung")).toBeInTheDocument()
    expect(screen.getByText("Keine Websuche mit Rohidee")).toBeInTheDocument()
    expect(screen.getByText("Keine Prompts/Rohdaten im UI")).toBeInTheDocument()
    expect(screen.getByText("Mensch prüft kritische Punkte")).toBeInTheDocument()
    expect(
      screen.queryByText(/Nicht jeder Agent sieht alle Daten/)
    ).not.toBeInTheDocument()
  })

  it("markiert Phasen mit menschlicher Prüfung", () => {
    render(<KiTeamScreen />)
    expect(screen.getAllByText("Sie prüfen").length).toBeGreaterThan(0)
  })
})
