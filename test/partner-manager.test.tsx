import * as React from "react"
import { act, screen, waitFor } from "@testing-library/react"
import { renderToString } from "react-dom/server"
import { hydrateRoot, type Root } from "react-dom/client"
import { http, HttpResponse } from "msw"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { AppProviders } from "@/components/providers/app-providers"
import { PartnerManager } from "@/components/partner/partner-manager"
import { server } from "./server"

const replace = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  usePathname: () => "/partner",
}))

const SESSION = {
  user: {
    user_id: "user-anna",
    name: "Anna Keller",
    email: "anna.keller@example.test",
    effective_role: "lead_admin",
    display_label: "Anna Keller",
  },
  csrf_token: "tok",
}

function projectBody(overrides: Record<string, unknown> = {}) {
  return {
    project_id: "p-1",
    workspace_id: "ws-demo",
    title: "Testprojekt",
    description: "Idee",
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
    ...overrides,
  }
}

function App() {
  return (
    <AppProviders mode="live">
      <PartnerManager />
    </AppProviders>
  )
}

describe("PartnerManager hydration", () => {
  beforeEach(() => {
    replace.mockReset()
    window.localStorage.clear()
    window.sessionStorage.clear()
    window.sessionStorage.setItem("rf_active_project_id", "p-1")
    server.use(
      http.get("/api/session", () => HttpResponse.json(SESSION)),
      http.get("/api/projects", () =>
        HttpResponse.json({ items: [projectBody()], next_cursor: null })
      ),
      http.get("/api/projects/p-1", () => HttpResponse.json(projectBody())),
      http.get("/api/projects/p-1/partners", () => HttpResponse.json([]))
    )
  })

  it("keeps the initial server render independent of sessionStorage", () => {
    const html = renderToString(<App />)

    expect(html).toContain("Partner &amp; Budget")
    expect(html).not.toContain("Budget &amp; Laufzeit")
  })

  it("hydrates without adding BudgetForm during the first client render", async () => {
    const html = renderToString(<App />)
    const container = document.createElement("div")
    container.innerHTML = html
    document.body.appendChild(container)
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    let root: Root | null = null

    await act(async () => {
      root = hydrateRoot(container, <App />)
      await Promise.resolve()
    })

    await waitFor(() =>
      expect(screen.getByText("Budget & Laufzeit")).toBeInTheDocument()
    )
    const hydrationErrors = errorSpy.mock.calls
      .flat()
      .map(String)
      .filter((message) => message.includes("Hydration failed"))
    expect(hydrationErrors).toEqual([])

    errorSpy.mockRestore()
    await act(async () => {
      root?.unmount()
    })
    container.remove()
  })
})
