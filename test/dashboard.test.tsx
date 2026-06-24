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

describe("dashboard live demo projects", () => {
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

  it("shows demo badges and truthful next actions", async () => {
    render(
      <AppProviders mode="live">
        <DashboardPage />
      </AppProviders>
    )

    await screen.findByText(/kreislauffaehiger Verbundwerkstoffe/)
    expect(screen.getAllByText("Demo")).toHaveLength(2)
    expect(
      screen.getByRole("button", { name: "Entwurf weiterbearbeiten" })
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Analyse/ })).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Review freigeben" })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Export erstellen" })
    ).not.toBeInTheDocument()
  })

  it("sets the active project before navigating", async () => {
    render(
      <AppProviders mode="live">
        <DashboardPage />
      </AppProviders>
    )

    const action = await screen.findByRole("button", {
      name: "Entwurf weiterbearbeiten",
    })
    fireEvent.click(action)

    expect(window.sessionStorage.getItem("rf_active_project_id")).toBe("project-a")
    await waitFor(() => expect(push).toHaveBeenCalledWith("/editor"))
  })
})
