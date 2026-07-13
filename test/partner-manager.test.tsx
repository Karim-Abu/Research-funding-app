import * as React from "react"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
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

function partnerBody(overrides: Record<string, unknown> = {}) {
  return {
    partner_id: "pr-1",
    project_id: "p-1",
    name: "ETH Zürich",
    partner_type: "research_partner",
    project_role: "Grundlagenforschung",
    country: "CH",
    location: null,
    department: null,
    contribution: "Langjährige Erfahrung in Leistungselektronik.",
    uid: null,
    industry: null,
    fte: null,
    startup_status: null,
    swiss_value_creation: null,
    research_partner_eligibility_status: "eligible",
    official_representative: null,
    personnel_independence_status: null,
    financial_independence_status: null,
    review_comment: null,
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

function fillBaseFields() {
  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: "Industrie AG" },
  })
  fireEvent.change(screen.getByLabelText("Land"), { target: { value: "CH" } })
  fireEvent.change(screen.getByLabelText("Rolle im Projekt"), {
    target: { value: "Umsetzung" },
  })
  fireEvent.change(screen.getByLabelText("Kompetenz & Beitrag (kurz)"), {
    target: { value: "Baut den Prototyp." },
  })
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
      http.get("/api/projects/p-1/partners", () => HttpResponse.json([])),
      http.get("/api/projects/p-1/structured-imports/summary", () =>
        HttpResponse.json({
          partners: { detected: 0, reviewed: 0, unchecked: 0 },
          budget: { detected: 0, reviewed: 0, unchecked: 0 },
          provenance: [],
        })
      ),
      http.get("/api/projects/p-1/budget/precheck", () =>
        HttpResponse.json({
          figures: {
            direct_costs_chf: null,
            own_contribution_chf: null,
            cash_contribution_chf: null,
            requested_funding_chf: null,
            implementation_contribution_chf: null,
            implementation_share_percent: null,
            cash_share_percent: null,
            funding_share_percent: null,
            exception_claimed: false,
          },
          checks: [],
        })
      )
    )
  })

  it("keeps the initial server render independent of sessionStorage", () => {
    const html = renderToString(<App />)

    expect(html).toContain("Partner &amp; Budget")
    expect(html).not.toContain("Budget &amp; Laufzeit")
  })

  it("erzwingt die MVP-Pflichtfelder mit erklärtem Disabled-Zustand", async () => {
    render(<App />)
    const submit = await screen.findByRole("button", {
      name: "Partner hinzufügen",
    })
    expect(submit).toBeDisabled()
    expect(
      screen.getByText(
        "Noch offen: Name, Land, Rolle im Projekt, Kompetenz & Beitrag."
      )
    ).toBeInTheDocument()

    fillBaseFields()
    await waitFor(() => expect(submit).toBeEnabled())
    expect(screen.queryByText(/Noch offen:/)).not.toBeInTheDocument()
  })

  it("verlangt bei «Angabe nötig» einen Kommentar und sendet ihn mit", async () => {
    let created: Record<string, unknown> | null = null
    server.use(
      http.post("/api/projects/p-1/partners", async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(
          partnerBody({ ...created, partner_id: "pr-2" }),
          { status: 201 }
        )
      })
    )
    render(<App />)
    await screen.findByRole("button", { name: "Partner hinzufügen" })
    fillBaseFields()

    // Detailfragen sind progressiv eingeklappt.
    expect(screen.queryByLabelText("Personelle Unabhängigkeit")).toBeNull()
    fireEvent.click(
      screen.getByRole("button", { name: "Unabhängigkeit (Detailangaben)" })
    )
    fireEvent.change(
      await screen.findByLabelText("Personelle Unabhängigkeit"),
      { target: { value: "needs_input" } }
    )

    // «unklar» ohne Kommentar → Submit bleibt gesperrt und erklärt warum.
    const submit = screen.getByRole("button", { name: "Partner hinzufügen" })
    expect(submit).toBeDisabled()
    expect(
      screen.getByText("Noch offen: Kommentar zur Einstufung.")
    ).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("Kommentar zur Einstufung"), {
      target: { value: "Beteiligung wird noch geklärt." },
    })
    await waitFor(() => expect(submit).toBeEnabled())
    fireEvent.click(submit)
    await waitFor(() => expect(created).not.toBeNull())
    expect(created!.personnel_independence_status).toBe("needs_input")
    expect(created!.review_comment).toBe("Beteiligung wird noch geklärt.")
  })

  it("bearbeitet einen bestehenden Partner über PATCH", async () => {
    let patched: Record<string, unknown> | null = null
    server.use(
      http.get("/api/projects/p-1/partners", () =>
        HttpResponse.json([partnerBody()])
      ),
      http.patch("/api/partners/pr-1", async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(partnerBody(patched ?? {}))
      })
    )
    render(<App />)
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Partner ETH Zürich bearbeiten",
      })
    )
    // Formular ist vorbefüllt; der Submit-Button wechselt in den Edit-Modus.
    expect(screen.getByLabelText("Name")).toHaveValue("ETH Zürich")
    fireEvent.change(screen.getByLabelText("Rolle im Projekt"), {
      target: { value: "Simulation und Validierung" },
    })
    fireEvent.click(
      screen.getByRole("button", { name: "Änderungen speichern" })
    )
    await waitFor(() => expect(patched).not.toBeNull())
    expect(patched!.name).toBe("ETH Zürich")
    expect(patched!.project_role).toBe("Simulation und Validierung")
  })

  it("übersetzt die Beitragsberechtigung und markiert menschliche Prüfung", async () => {
    server.use(
      http.get("/api/projects/p-1/partners", () =>
        HttpResponse.json([
          partnerBody({
            research_partner_eligibility_status: "needs_verification",
            review_comment: "Trägerstatus wird abgeklärt.",
          }),
        ])
      )
    )
    render(<App />)
    // Deutsche Anzeige, nie der rohe Enum-Wert.
    expect(await screen.findByText("zu prüfen")).toBeInTheDocument()
    expect(screen.queryByText("needs_verification")).not.toBeInTheDocument()
    // Qualitative Angabe → HITL-Markierung, kein automatisches Urteil.
    expect(
      screen.getByText("Menschliche Prüfung erforderlich")
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Trägerstatus wird abgeklärt\./)
    ).toBeInTheDocument()
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

  it("zeigt die sichere PDF-Zusammenfassung und menschlich bestätigte Provenienz", async () => {
    server.use(
      http.get("/api/projects/p-1/partners", () =>
        HttpResponse.json([partnerBody({ department: "Applied Systems" })])
      ),
      http.get("/api/projects/p-1/structured-imports/summary", () =>
        HttpResponse.json({
          partners: { detected: 3, reviewed: 1, unchecked: 2 },
          budget: { detected: 5, reviewed: 2, unchecked: 3 },
          provenance: [
            {
              candidate_kind: "partner",
              target_key: "partner.research.01",
              applied_resource_id: "pr-1",
              source_location: "Seite 3",
              state: "confirmed",
            },
          ],
        })
      )
    )
    render(<App />)
    const summary = await screen.findByTestId("structured-import-summary")
    expect(summary).toHaveTextContent("Aus PDF erkannt: 3 Partner, 5 Budgetangaben")
    expect(summary).toHaveTextContent("Geprüft: 3; ungeprüft: 5")
    expect(screen.getByRole("link", { name: "Zum Importreview" })).toHaveAttribute(
      "href",
      "/import#strukturierte-kandidaten"
    )
    expect(
      screen.getByText("Aus PDF übernommen – Seite 3 – menschlich bestätigt")
    ).toBeInTheDocument()
    expect(screen.getByText(/Applied Systems/)).toBeInTheDocument()
  })
})
