import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
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
const shellProjects = [{ id: "project-a", title: "Verbundwerkstoffe (Demo)" }]

function setCompactViewport(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

function renderMockShell() {
  return render(
    <AppProviders mode="mock">
      <AppShell user={user} projects={shellProjects} activeProjectId="project-a">
        <div>content</div>
      </AppShell>
    </AppProviders>
  )
}

async function flushProviderEffects() {
  await act(async () => {
    await Promise.resolve()
  })
}

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
    window.localStorage.clear()
    setCompactViewport(false)
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
      ),
      // WorkflowRunProvider (zentrale Run-Auswahl) lädt Projekt, Runs und
      // Partner des aktiven Antrags.
      http.get("/api/projects/project-a", () =>
        HttpResponse.json(project("project-a", "Verbundwerkstoffe (Demo)"))
      ),
      http.get("/api/projects/project-a/runs", () =>
        HttpResponse.json({ items: [], next_cursor: null })
      ),
      http.get("/api/projects/project-a/partners", () => HttpResponse.json([]))
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
    // «Projekt anlegen» stays reachable to create a new Antrag.
    expect(
      screen.getAllByRole("link", { name: "Projekt anlegen" }).length
    ).toBeGreaterThan(0)
  })

  it("starts expanded on desktop and collapses to the icon rail", async () => {
    renderMockShell()
    await flushProviderEffects()

    const toggle = screen.getByRole("button", { name: "Minimieren" })
    expect(toggle).toHaveAttribute("aria-expanded", "true")
    expect(screen.getByText("Funding Programme")).toBeInTheDocument()
    expect(screen.getByTestId("sidebar-active-project")).toHaveTextContent(
      "Verbundwerkstoffe (Demo)"
    )

    fireEvent.click(toggle)

    expect(window.localStorage.getItem("rf_sidebar_collapsed")).toBe("true")
    expect(screen.getByRole("button", { name: "Erweitern" })).toHaveAttribute(
      "aria-expanded",
      "false"
    )
    expect(screen.queryByText("Funding Programme")).toBeNull()
    expect(screen.getByRole("link", { name: "Quellen" })).toBeInTheDocument()
  })

  it("restores the persisted collapsed state", async () => {
    window.localStorage.setItem("rf_sidebar_collapsed", "true")
    const { unmount } = renderMockShell()
    await flushProviderEffects()

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Erweitern" })).toHaveAttribute(
        "aria-expanded",
        "false"
      )
    )
    expect(screen.queryByText("Funding Programme")).toBeNull()

    unmount()
    renderMockShell()
    await flushProviderEffects()

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Erweitern" })).toBeInTheDocument()
    )
  })

  it("starts collapsed on compact screens when no preference is stored", async () => {
    setCompactViewport(true)

    renderMockShell()
    await flushProviderEffects()

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Erweitern" })).toHaveAttribute(
        "aria-expanded",
        "false"
      )
    )
    expect(window.localStorage.getItem("rf_sidebar_collapsed")).toBeNull()
    expect(screen.queryByText("Funding Programme")).toBeNull()
    expect(screen.getByRole("link", { name: "Quellen" })).toBeInTheDocument()
  })
})
