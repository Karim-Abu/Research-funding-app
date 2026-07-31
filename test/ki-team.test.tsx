import { describe, expect, it } from "vitest"
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { KiTeamScreen } from "@/components/ki-team/ki-team-page"
import {
  getKiTeamPhases,
  getRoleCatalogGroups,
  kiTeamRoles,
  kiTeamTexts,
  MODEL_ROUTE_NOTICE,
  phaseAssignments,
} from "@/lib/ki-team-data"
import { WORKFLOW_STEPS } from "@/lib/workflow"

function collectStrings(value: unknown): string[] {
  if (typeof value === "string") return [value]
  if (Array.isArray(value)) return value.flatMap(collectStrings)
  if (value && typeof value === "object") {
    return Object.values(value).flatMap(collectStrings)
  }
  return []
}

describe("Rollen- und Funktionskatalog", () => {
  it("enthält exakt zehn eindeutige Systemrollen ohne menschliche Pseudo-Rolle", () => {
    const ids = new Set(kiTeamRoles.map((role) => role.id))
    const names = new Set(kiTeamRoles.map((role) => role.name))

    expect(kiTeamRoles).toHaveLength(10)
    expect(ids.size).toBe(10)
    expect(names.size).toBe(10)
    expect(
      kiTeamRoles.some(
        (role) =>
          role.id.toLocaleLowerCase() === "sie" ||
          role.name.toLocaleLowerCase() === "sie"
      )
    ).toBe(false)
  })

  it("hinterlegt für jede Rolle Modus, Fachicon, Phasen und technische Zuordnung", () => {
    for (const role of kiTeamRoles) {
      expect(["ki", "regelbasiert", "hybrid"]).toContain(role.mode)
      expect(role.iconKey).toBeTruthy()
      expect(role.activeSteps.length).toBeGreaterThan(0)
      expect(role.technicalComponents.length).toBeGreaterThan(0)
      expect(role.specialization).toBeTruthy()
      expect(role.outputSummary).toBeTruthy()
    }
  })

  it("ordnet KI- und Hybridfunktionen einer Modellroute und feste Dienste keiner KI zu", () => {
    for (const role of kiTeamRoles) {
      if (role.mode === "regelbasiert") {
        expect(role.modelInfo.kind).toBe("none")
        if (role.modelInfo.kind === "none") {
          expect(role.modelInfo.description).toMatch(/^Kein KI-Modell\./)
        }
        continue
      }

      expect(role.modelInfo.kind).toBe("model-route")
      if (role.modelInfo.kind === "model-route") {
        expect(role.modelInfo.primary.model).toBeTruthy()
        expect(role.modelInfo.primary.provider).toBeTruthy()
        expect(role.modelInfo.fallback?.model).toBeTruthy()
        expect(role.modelInfo.fallback?.provider).toBeTruthy()
      }
    }
  })

  it("verwendet die kanonischen Primär- und Ersatzmodelle nur für passende Funktionen", () => {
    const routes = Object.fromEntries(
      kiTeamRoles
        .filter((role) => role.modelInfo.kind === "model-route")
        .map((role) => {
          if (role.modelInfo.kind !== "model-route") {
            throw new Error(`Fehlende Modellroute für ${role.id}`)
          }
          return [
            role.id,
            {
              primary: role.modelInfo.primary,
              fallback: role.modelInfo.fallback,
            },
          ]
        })
    )

    expect(routes).toEqual({
      "marktrecherche-assistent": {
        primary: { provider: "Anthropic", model: "Claude Sonnet 5" },
        fallback: { provider: "Anthropic", model: "Claude Haiku 4.5" },
      },
      anforderungsanalyst: {
        primary: { provider: "OpenAI", model: "GPT-5.6 Luna" },
        fallback: { provider: "Anthropic", model: "Claude Haiku 4.5" },
      },
      evidenzpruefer: {
        primary: { provider: "OpenAI", model: "GPT-5.6 Luna" },
        fallback: { provider: "Anthropic", model: "Claude Haiku 4.5" },
      },
      "innovationstext-assistent": {
        primary: { provider: "Anthropic", model: "Claude Sonnet 5" },
        fallback: { provider: "OpenAI", model: "GPT-5.6 Terra" },
      },
      qualitaetskoordinator: {
        primary: { provider: "OpenAI", model: "GPT-5.6 Terra" },
        fallback: { provider: "Anthropic", model: "Claude Sonnet 5" },
      },
    })
  })

  it("begrenzt den KI-Anteil der Marktrecherche auf die Quellenstrukturierung", () => {
    const research = kiTeamRoles.find(
      (role) => role.id === "marktrecherche-assistent"
    )

    expect(research?.modelInfo.kind).toBe("model-route")
    if (research?.modelInfo.kind === "model-route") {
      expect(research.modelInfo.scope).toContain(
        "Nur die Strukturierung übernommener öffentlicher Quellen ist KI-gestützt"
      )
      expect(research.modelInfo.scope).toContain(
        "Planung, Schutzprüfung und Rechercheausführung bleiben regelbasiert"
      )
    }
  })

  it("ordnet A1, A2 und A3 nur den belegten sichtbaren Funktionen zu", () => {
    const rolesFor = (technicalPrefix: string) =>
      kiTeamRoles
        .filter((role) =>
          role.technicalComponents.some((component) =>
            component.startsWith(technicalPrefix)
          )
        )
        .map((role) => role.id)

    expect(rolesFor("A1.")).toEqual([
      "anforderungsanalyst",
      "evidenzpruefer",
    ])
    expect(rolesFor("A2 ")).toEqual(["innovationstext-assistent"])
    expect(rolesFor("A3.")).toEqual(["qualitaetskoordinator"])
  })

  it("modelliert Qualitätskoordination hybrid und erfindet keine Anforderungen", () => {
    const quality = kiTeamRoles.find(
      (role) => role.id === "qualitaetskoordinator"
    )
    const requirements = kiTeamRoles.find(
      (role) => role.id === "anforderungsanalyst"
    )

    expect(quality?.mode).toBe("hybrid")
    expect(requirements?.decisionBoundary).toContain(
      "Definiert keine offiziellen Anforderungen"
    )
    expect(
      `${requirements?.specialization} ${requirements?.task}`
    ).not.toMatch(/erstellt|erfindet|definiert offizielle Anforderungen/i)
  })

  it("verwendet die sechs kanonischen Workflow-Schritte und ordnet jede Rolle zu", () => {
    const phases = getKiTeamPhases()

    expect(phases).toHaveLength(6)
    expect(phases.map((phase) => phase.step)).toEqual([...WORKFLOW_STEPS])

    const usedIds = new Set(
      phases.flatMap((phase) => phase.roles.map((role) => role.id))
    )
    expect(usedIds.size).toBe(10)

    for (const role of kiTeamRoles) {
      const assignedSteps = phaseAssignments
        .filter((phase) => phase.roleIds.includes(role.id))
        .map((phase) => phase.step)
      expect(assignedSteps).toEqual(role.activeSteps)
    }
  })

  it("gruppiert acht Fachfunktionen und zwei Systemfunktionen", () => {
    const groups = getRoleCatalogGroups()

    expect(groups.map((group) => group.title)).toEqual([
      "Fachliche Spezialisten",
      "System & Schutz",
    ])
    expect(groups[0].roles).toHaveLength(8)
    expect(groups[1].roles).toHaveLength(2)
  })
})

describe("Wording-Grenzen", () => {
  const corpus = [...collectStrings(kiTeamRoles), ...collectStrings(kiTeamTexts)]

  it("enthält keine Autonomie- oder Erfolgsversprechen", () => {
    const forbidden = [
      /zehn spezialisierte Agenten/i,
      /autonom/i,
      /vollautomatisch/i,
      /Erfolgschance/i,
      /Bewilligungswahrscheinlichkeit/i,
      /bewertet Ihre Chancen/i,
      /reicht (den|einen) Antrag automatisch ein/i,
      /synchronisiert (automatisch )?mit Innolink/i,
    ]
    for (const text of corpus) {
      for (const pattern of forbidden) {
        expect(text).not.toMatch(pattern)
      }
    }
  })

  it("nennt Förderwahrscheinlichkeit nur als ausdrückliche Grenze", () => {
    const neverPoints = new Set<string>(kiTeamTexts.neverDecides.points)
    for (const text of corpus) {
      if (/Förderwahrscheinlichkeit/i.test(text)) {
        expect(
          /keine|bestätigt keine|nie/i.test(text) || neverPoints.has(text),
          `Riskante Verwendung: ${text}`
        ).toBe(true)
      }
    }
  })

  it("stellt menschliche Übernahme von KI-Texten ausdrücklich sicher", () => {
    const drafting = kiTeamRoles.find(
      (role) => role.id === "innovationstext-assistent"
    )
    expect(drafting?.humanReview).toBe(
      "Sie übernehmen, bearbeiten oder verwerfen jeden Vorschlag ausdrücklich."
    )
    expect(drafting?.decisionBoundary).toContain(
      "Ändert keinen Feldtext automatisch"
    )
  })
})

describe("Responsibility-Cockpit", () => {
  it("rendert den neuen Kopf und die kompakte Verantwortungsübersicht", () => {
    render(<KiTeamScreen />)

    expect(
      screen.getByRole("heading", { name: "Rollen & Verantwortung" })
    ).toBeInTheDocument()
    expect(screen.getByText(kiTeamTexts.subtitle)).toBeInTheDocument()
    expect(screen.getByText("Forschungsprototyp")).toBeInTheDocument()
    expect(screen.getByText("KI unterstützt")).toBeInTheDocument()
    expect(screen.getByText("Regeln prüfen")).toBeInTheDocument()
    expect(screen.getByText("Menschen entscheiden")).toBeInTheDocument()
  })

  it("zeigt drei Tabs und aktiviert Im Ablauf initial", () => {
    render(<KiTeamScreen />)

    const workflow = screen.getByRole("tab", { name: "Im Ablauf" })
    expect(workflow).toHaveAttribute("aria-selected", "true")
    expect(screen.getByRole("tab", { name: "Spezialisten" })).toBeInTheDocument()
    expect(
      screen.getByRole("tab", { name: "Ihre Freigaben" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("heading", {
        name: "Verantwortungen entlang des Ablaufs",
      })
    ).toBeInTheDocument()
  })

  it("wechselt die Tabs per Tastatur", async () => {
    render(<KiTeamScreen />)

    const workflow = screen.getByRole("tab", { name: "Im Ablauf" })
    act(() => {
      workflow.focus()
      fireEvent.keyDown(workflow, { key: "ArrowRight" })
    })

    const specialists = screen.getByRole("tab", { name: "Spezialisten" })
    await waitFor(() => expect(specialists).toHaveFocus())
  })

  it("zeigt pro Phase Ergebnis und konkrete menschliche Aufgabe", () => {
    render(<KiTeamScreen />)

    for (const assignment of phaseAssignments) {
      expect(screen.getByText(assignment.result)).toBeInTheDocument()
      expect(screen.getByText(assignment.humanAction)).toBeInTheDocument()
    }
    expect(screen.queryByText("Sie prüfen")).not.toBeInTheDocument()
  })

  it("zeigt Spezialisten einmalig und nach Kategorie gruppiert", async () => {
    render(<KiTeamScreen />)
    fireEvent.click(screen.getByRole("tab", { name: "Spezialisten" }))

    expect(
      await screen.findByRole("heading", { name: "Fachliche Spezialisten" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("heading", { name: "System & Schutz" })
    ).toBeInTheDocument()

    for (const role of kiTeamRoles) {
      expect(
        screen.getAllByRole("button", {
          name: new RegExp(`^${role.name}:`),
        })
      ).toHaveLength(1)
    }
  })

  it("zeigt alle menschlichen Kontrollpunkte, Grenzen und Schutzregeln", async () => {
    render(<KiTeamScreen />)
    fireEvent.click(screen.getByRole("tab", { name: "Ihre Freigaben" }))

    expect(
      await screen.findByRole("heading", {
        name: "Ihre sechs Kontrollpunkte",
      })
    ).toBeInTheDocument()
    for (const assignment of phaseAssignments) {
      expect(screen.getByText(assignment.humanAction)).toBeInTheDocument()
    }
    expect(
      screen.getByRole("heading", { name: "Das System entscheidet nie" })
    ).toBeInTheDocument()
    for (const point of kiTeamTexts.neverDecides.points) {
      expect(screen.getByText(point)).toBeInTheDocument()
    }
    for (const point of kiTeamTexts.dataProtection.points) {
      expect(screen.getByText(point)).toBeInTheDocument()
    }
  })

  it("öffnet den Drawer, zeigt Fachinformationen und gibt den Fokus zurück", async () => {
    render(<KiTeamScreen />)
    const card = screen.getAllByRole("button", {
      name: /^Anforderungsanalyst:/,
    })[0]

    fireEvent.click(card)
    const dialog = await screen.findByRole("dialog")
    for (const heading of [
      "Aufgabe",
      "Ergebnis",
      "Ihre Entscheidung",
      "Entscheidungsgrenze",
      "Aktiv in",
    ]) {
      expect(
        within(dialog).getByRole("heading", { name: heading })
      ).toBeInTheDocument()
    }
    expect(dialog).toHaveClass("data-[side=right]:sm:w-[560px]")
    const dataTrigger = within(dialog).getByRole("button", {
      name: "Daten & Rahmen",
    })
    expect(dataTrigger).toHaveAttribute("aria-expanded", "false")
    expect(within(dialog).queryByRole("heading", { name: "Datenzugriff" })).toBeNull()
    fireEvent.click(dataTrigger)
    expect(
      await within(dialog).findByRole("heading", { name: "Arbeitsgrundlage" })
    ).toBeVisible()
    expect(
      within(dialog).getByRole("heading", { name: "Datenzugriff" })
    ).toBeVisible()
    expect(card).toHaveAttribute("aria-expanded", "true")

    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    await waitFor(() => expect(card).toHaveFocus())
  })

  it("hält Modelle, Provider, interne Komponenten und Quellpfade eingeklappt", async () => {
    render(<KiTeamScreen />)
    expect(screen.queryByText("GPT-5.6 Luna")).toBeNull()
    expect(screen.queryByText("OpenAI")).toBeNull()
    expect(screen.queryByText("A1.project_fact_extraction")).toBeNull()
    expect(screen.queryByText(/backend\/app\/agents\/fact_extraction/)).toBeNull()

    fireEvent.click(
      screen.getAllByRole("button", {
        name: /^Anforderungsanalyst:/,
      })[0]
    )
    const dialog = await screen.findByRole("dialog")
    const trigger = within(dialog).getByRole("button", {
      name: "Technische Details",
    })
    expect(trigger).toHaveAttribute("aria-expanded", "false")
    expect(within(dialog).queryByText("GPT-5.6 Luna")).toBeNull()
    expect(within(dialog).queryByText("OpenAI")).toBeNull()
    expect(within(dialog).queryByText("A1.project_fact_extraction")).toBeNull()

    fireEvent.click(trigger)
    expect(
      await within(dialog).findByRole("heading", { name: "KI-Modell" })
    ).toBeVisible()
    expect(within(dialog).getByText("Primär vorgesehen")).toBeVisible()
    expect(within(dialog).getByText("GPT-5.6 Luna")).toBeVisible()
    expect(within(dialog).getByText("OpenAI")).toBeVisible()
    expect(within(dialog).getByText("Ersatzroute")).toBeVisible()
    expect(within(dialog).getByText("Claude Haiku 4.5")).toBeVisible()
    expect(within(dialog).getByText("Anthropic")).toBeVisible()
    expect(within(dialog).getByText(MODEL_ROUTE_NOTICE)).toBeVisible()
    expect(
      within(dialog).getByRole("heading", { name: "Ausführungslogik" })
    ).toBeVisible()
    expect(
      await within(dialog).findByText("A1.project_fact_extraction")
    ).toBeVisible()
    expect(
      within(dialog).getByText(/backend\/app\/agents\/fact_extraction/)
    ).toBeVisible()
  })

  it("weist bei regelbasierten Funktionen ausdrücklich aus, dass kein KI-Modell läuft", async () => {
    render(<KiTeamScreen />)
    fireEvent.click(
      screen.getAllByRole("button", {
        name: /^Workflow-Koordinator:/,
      })[0]
    )

    const dialog = await screen.findByRole("dialog")
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Technische Details" })
    )

    expect(
      await within(dialog).findByText(
        "Kein KI-Modell. Die Funktion folgt einer fest definierten Ablaufsteuerung."
      )
    ).toBeVisible()
    expect(within(dialog).queryByText(MODEL_ROUTE_NOTICE)).toBeNull()
  })

  it("rendert keine alten Entwicklungsnamen oder technischen Standardtexte", () => {
    render(<KiTeamScreen />)
    const removedTexts = [
      "Demo-Modus",
      "Einfach",
      "Details",
      "Fakten-Leser (A1)",
      "Text-Vorschlager (A2)",
      "Prüf-Zusammenfasser (A3)",
      "Sie (menschliche Prüfung)",
      "Letzter Lauf",
      "Noch kein Lauf",
    ]

    for (const text of removedTexts) {
      expect(screen.queryByText(text, { exact: true })).toBeNull()
    }
  })
})
