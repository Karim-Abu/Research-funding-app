// Konsistente Schrittbezeichnung: Stepper und Sidebar lesen ihre Labels aus
// dem EINEN Katalog (lib/workflow.ts) — eine Route hat überall denselben
// sichtbaren Namen.

import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { AppProviders } from "@/components/providers/app-providers"
import { WorkflowRunProvider } from "@/components/providers/workflow-run-provider"
import { Sidebar } from "@/components/shell/sidebar"
import { WorkflowStepper } from "@/components/shell/workflow-stepper"
import { WORKFLOW_STEPS } from "@/lib/workflow"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/quellen",
}))

function renderStepper() {
  return render(
    <AppProviders mode="mock">
      <WorkflowRunProvider>
        <WorkflowStepper />
      </WorkflowRunProvider>
    </AppProviders>
  )
}

describe("Workflow-Namensgebung (ein Katalog, ein Name pro Route)", () => {
  it("der Stepper zeigt genau die 6 Katalog-Schritte", () => {
    renderStepper()
    const nav = screen.getByRole("navigation", { name: "Arbeitsschritte" })
    for (const step of WORKFLOW_STEPS) {
      expect(nav).toHaveTextContent(step.label)
    }
    // Alte konkurrierende Hauptschritte existieren nicht mehr.
    expect(nav).not.toHaveTextContent("Evidenz")
    expect(nav.querySelectorAll("li")).toHaveLength(WORKFLOW_STEPS.length)
  })

  it("der Stepper zeigt keine Roh-Run-ID", () => {
    renderStepper()
    const nav = screen.getByRole("navigation", { name: "Arbeitsschritte" })
    expect(nav.textContent).not.toMatch(/run[-_]?id/i)
  })

  it("die Sidebar führt die Schritte 2–6 mit den Katalog-Labels", () => {
    render(
      <Sidebar
        collapsed={false}
        onToggle={() => {}}
        activeProjectTitle="Testprojekt"
        activeProjectStatusLabel="In Bearbeitung"
      />
    )
    for (const step of WORKFLOW_STEPS.filter((s) => s.step >= 2)) {
      expect(
        screen.getByRole("link", { name: step.label }),
        step.label
      ).toBeInTheDocument()
    }
    // Schritt 1 erscheint mit seinen Routennamen (ein Name pro Route).
    expect(screen.getAllByRole("link", { name: "Projekt anlegen" }).length)
      .toBeGreaterThan(0)
    expect(screen.getByRole("link", { name: "Antrag importieren" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Quellen" })).toBeInTheDocument()
    // «Evidenz» ist kein eigener Navigationspunkt mehr.
    expect(screen.queryByRole("link", { name: "Evidenz" })).toBeNull()
  })
})
