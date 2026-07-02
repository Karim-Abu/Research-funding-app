import { render, screen, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { AppProviders } from "@/components/providers/app-providers"
import { AppShell } from "@/components/shell/app-shell"
import { server } from "./server"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/quellen",
}))

const user = { name: "Anna Keller", displayRole: "Lead", role: "lead_admin" as const }

function project(id: string, title: string) {
  return {
    project_id: id,
    workspace_id: "ws-demo",
    title,
    description: "d",
    funding_instrument_profile_id: "innosuisse",
    data_classification: {
      sensitivity: "public",
      origin: "synthetic",
      processing_mode: "deterministic_only",
      web_research_mode: "off",
      nda_applies: false,
    },
    status: "draft",
    created_at: "2026-06-24T10:00:00.000Z",
    updated_at: "2026-06-24T10:00:00.000Z",
    active_run_id: null,
  }
}

describe("active Antrag context (M10.2)", () => {
  beforeEach(() => {
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
          items: [project("project-a", "Verbundwerkstoffe (Demo)")],
          next_cursor: null,
        })
      )
    )
  })

  it("shows the active Antrag title in sidebar and switcher", async () => {
    window.sessionStorage.setItem("rf_active_project_id", "project-a")
    render(
      <AppProviders mode="live">
        <AppShell user={user} projects={[]} activeProjectId="">
          <div>content</div>
        </AppShell>
      </AppProviders>
    )

    await waitFor(() =>
      expect(screen.getByTestId("sidebar-active-project")).toHaveTextContent(
        "Verbundwerkstoffe (Demo)"
      )
    )
    expect(screen.getByTestId("active-project-switcher")).toHaveTextContent(
      "Verbundwerkstoffe (Demo)"
    )
    // Section header (sidebar) + switcher label (topbar).
    expect(screen.getAllByText("Aktueller Antrag").length).toBeGreaterThanOrEqual(2)
    // Project-scoped links are enabled.
    expect(screen.getByRole("link", { name: "Quellen" })).toBeInTheDocument()
  })

  it("disables project links and prompts selection when no Antrag is active", async () => {
    render(
      <AppProviders mode="live">
        <AppShell user={user} projects={[]} activeProjectId="">
          <div>content</div>
        </AppShell>
      </AppProviders>
    )

    await waitFor(() =>
      expect(screen.getByTestId("sidebar-active-project")).toHaveTextContent(
        "Kein Antrag ausgewählt"
      )
    )
    expect(screen.getByTestId("active-project-switcher")).toHaveTextContent(
      "Antrag auswählen"
    )
    // Project-scoped items render disabled with the selection hint.
    expect(screen.queryByRole("link", { name: "Quellen" })).toBeNull()
    expect(screen.getAllByText("Zuerst Antrag auswählen").length).toBeGreaterThan(0)
    // Intake stays reachable to create a new Antrag.
    expect(screen.getByRole("link", { name: "Intake" })).toBeInTheDocument()
  })
})
