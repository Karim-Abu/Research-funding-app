import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { AppProviders } from "@/components/providers/app-providers"
import DashboardPage from "@/app/page"
import { server } from "./server"

const push = vi.fn()
const replace = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  usePathname: () => "/",
}))

const now = "2026-06-24T10:00:00.000Z"

function project(overrides: Record<string, unknown>) {
  return {
    project_id: "project-a",
    workspace_id: "ws-demo",
    title: "Project",
    description: "Synthetic demo project.",
    funding_instrument_profile_id: "innosuisse",
    data_classification: {
      sensitivity: "public",
      origin: "synthetic",
      processing_mode: "deterministic_only",
      web_research_mode: "off",
      nda_applies: false,
    },
    status: "draft",
    created_at: now,
    updated_at: now,
    active_run_id: null,
    ...overrides,
  }
}

describe("projects overview", () => {
  beforeEach(() => {
    push.mockReset()
    replace.mockReset()
    window.sessionStorage.clear()
    server.use(
      http.get("/api/session", () =>
        HttpResponse.json({
          user: {
            user_id: "user-anna",
            name: "Anna Keller",
            email: "anna.keller@example.test",
            effective_role: "lead_admin",
            display_label: "Anna Keller",
          },
          csrf_token: "tok",
        })
      ),
      http.get("/api/projects", () =>
        HttpResponse.json({
          items: [
            project({
              project_id: "project-a",
              title:
                "KI-gestuetzte Entwicklung kreislauffaehiger Verbundwerkstoffe (Demo)",
              workflow_summary: {
                bearbeitungsstand_percent: 72,
                current_step: 5,
                current_step_label: "Entwurf",
                next_action: "continue_draft",
                warning_badge: null,
                latest_run_id: "run-a",
              },
            }),
            project({
              project_id: "project-b",
              title: "Zustandsueberwachung fuer Produktionsanlagen (Demo)",
              workflow_summary: {
                bearbeitungsstand_percent: 45,
                current_step: 3,
                current_step_label: "Anforderungen",
                next_action: "review_analysis",
                warning_badge: null,
                latest_run_id: "run-b",
              },
            }),
          ],
          next_cursor: null,
        })
      )
    )
  })

  it("shows project cards and the compact overview", async () => {
    render(
      <AppProviders mode="live">
        <DashboardPage />
      </AppProviders>
    )

    await screen.findByText(/kreislauffaehiger Verbundwerkstoffe/)
    expect(
      screen.getByRole("heading", { name: "Projektübersicht" })
    ).toBeInTheDocument()
    expect(screen.getByText("Aktive Projekte")).toBeInTheDocument()
    // "Prüfung offen" appears as summary tile AND as filter chip since M10.2.
    expect(screen.getAllByText("Prüfung offen").length).toBeGreaterThan(0)
    expect(screen.getByText("Blocker")).toBeInTheDocument()
    expect(screen.getByText("Nächste Frist")).toBeInTheDocument()
    // 2 card badges + 1 filter chip (M10.2).
    expect(screen.getAllByText("Demo")).toHaveLength(3)
    expect(screen.getAllByRole("button", { name: "Weiterarbeiten" })).toHaveLength(2)
    expect(screen.getAllByText("Innosuisse · Innovationsprojekt")).toHaveLength(2)
    expect(screen.getByText(/Bearbeitungsstand:\s*72\s*%/)).toBeInTheDocument()
    // Backend step 5 (Entwurf) → UI step 6 (Partner & Budget inserted at 2).
    expect(screen.getByText(/Schritt 6 von 8:\s*Entwurf/)).toBeInTheDocument()
  })

  it("filters, searches and shows the warning badge (M10.2)", async () => {
    server.use(
      http.get("/api/projects", () =>
        HttpResponse.json({
          items: [
            project({
              project_id: "project-a",
              title: "Verbundwerkstoffe (Demo)",
              workflow_summary: {
                bearbeitungsstand_percent: 72,
                current_step: 5,
                current_step_label: "Entwurf",
                next_action: "continue_draft",
                warning_badge: null,
                latest_run_id: "run-a",
              },
            }),
            project({
              project_id: "project-user",
              title: "Eigener Antrag Robotik",
              workflow_summary: {
                bearbeitungsstand_percent: 10,
                current_step: 2,
                current_step_label: "Quellen",
                next_action: "resume_analysis",
                warning_badge: "run_stopped",
                latest_run_id: "run-u",
              },
            }),
          ],
          next_cursor: null,
        })
      )
    )
    render(
      <AppProviders mode="live">
        <DashboardPage />
      </AppProviders>
    )

    // A user-created project is first-class and shows the stopped-run warning.
    await screen.findByText("Eigener Antrag Robotik")
    expect(screen.getByText("Analyse gestoppt")).toBeInTheDocument()
    expect(screen.getByText(/Nächster Schritt: Analyse fortsetzen/)).toBeInTheDocument()

    // Search narrows the grid.
    fireEvent.change(screen.getByLabelText("Anträge durchsuchen"), {
      target: { value: "Robotik" },
    })
    expect(screen.queryByText("Verbundwerkstoffe (Demo)")).toBeNull()
    expect(screen.getByText("Eigener Antrag Robotik")).toBeInTheDocument()

    // Demo filter shows only demo projects (search cleared first).
    fireEvent.change(screen.getByLabelText("Anträge durchsuchen"), {
      target: { value: "" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Demo" }))
    expect(screen.getByText("Verbundwerkstoffe (Demo)")).toBeInTheDocument()
    expect(screen.queryByText("Eigener Antrag Robotik")).toBeNull()

    // Empty filter result offers a reset.
    fireEvent.change(screen.getByLabelText("Anträge durchsuchen"), {
      target: { value: "xyz-nicht-vorhanden" },
    })
    expect(
      screen.getByText(/Keine Anträge entsprechen der Suche/)
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Filter zurücksetzen" }))
    expect(screen.getByText("Eigener Antrag Robotik")).toBeInTheDocument()
  })

  it("sets the active project before navigating", async () => {
    render(
      <AppProviders mode="live">
        <DashboardPage />
      </AppProviders>
    )

    const action = (await screen.findAllByRole("button", {
      name: "Weiterarbeiten",
    }))[0]
    fireEvent.click(action)

    expect(window.sessionStorage.getItem("rf_active_project_id")).toBe("project-a")
    await waitFor(() => expect(push).toHaveBeenCalledWith("/editor"))
  })
})
