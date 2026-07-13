import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { AppProviders } from "@/components/providers/app-providers"
import QuellenPage from "@/app/quellen/page"
import { setBackendMode } from "@/lib/app-mode"
import { server } from "./server"

const push = vi.fn()
const replace = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  usePathname: () => "/quellen",
  useSearchParams: () => new URLSearchParams(),
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

// Live deployment without URL import: neither the feature flag nor the
// supported source type is present.
const CAPABILITIES_WITHOUT_URL = {
  api_version: "1.1.0",
  polling_interval_seconds: 2,
  max_upload_bytes: 10 * 1024 * 1024,
  supported_source_types: ["pdf", "docx", "txt"],
  features: { sources: true, url_import: false, runs: false },
}

const URL_INPUT = "https://www.innosuisse.admin.ch/innovation-projects"

describe("Quellen page URL fallback (live mode)", () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    window.sessionStorage.setItem("rf_active_project_id", "p1")
    server.use(
      http.get("/api/session", () => HttpResponse.json(SESSION)),
      http.get("/api/projects", () =>
        HttpResponse.json({ items: [], next_cursor: null })
      ),
      http.get("/api/capabilities", () =>
        HttpResponse.json(CAPABILITIES_WITHOUT_URL)
      ),
      http.get("/api/projects/p1/sources", () => HttpResponse.json([])),
      http.get("/api/projects/p1/runs", () =>
        HttpResponse.json({ items: [] })
      ),
      // WorkflowRunProvider (zentrale Run-Auswahl) lädt Projekt und Partner.
      http.get("/api/projects/p1", () =>
        HttpResponse.json({
          project_id: "p1",
          workspace_id: "ws-demo",
          title: "Projekt",
          description: "",
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
        })
      ),
      http.get("/api/projects/p1/partners", () => HttpResponse.json([]))
    )
  })
  afterEach(() => setBackendMode("mock"))

  it("shows the page hint instead of creating a fake source row", async () => {
    render(
      <AppProviders mode="live">
        <QuellenPage />
      </AppProviders>
    )

    // Wait for the live source table (capabilities + sources loaded).
    const addUrlButton = await screen.findByRole("button", {
      name: "URL hinzufügen",
    })
    fireEvent.click(addUrlButton)

    fireEvent.change(screen.getByLabelText("URL"), {
      target: { value: URL_INPUT },
    })
    fireEvent.click(screen.getByRole("button", { name: "Hinzufügen" }))

    await waitFor(() => {
      expect(
        screen.getByText(
          "URL-Import ist in dieser Umgebung nicht verfügbar. Kopieren Sie den Webseiteninhalt und fügen Sie ihn als Textquelle ein."
        )
      ).toBeInTheDocument()
    })

    // No fabricated table row for the URL, no pending fake status.
    expect(screen.queryByText(URL_INPUT)).not.toBeInTheDocument()
    expect(screen.queryByText(/Verarbeitung ausstehend/)).not.toBeInTheDocument()
  })
})
