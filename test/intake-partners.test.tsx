import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { AppProviders } from "@/components/providers/app-providers"
import { IntakeForm } from "@/components/intake/intake-form"
import { setBackendMode } from "@/lib/app-mode"
import { PARTNER_SAVE_HINT_KEY } from "@/lib/partners"
import { server } from "./server"

// jsdom lacks Element.scrollTo, which the intake form calls on mount.
if (typeof Element.prototype.scrollTo !== "function") {
  Element.prototype.scrollTo = () => {}
}

const push = vi.fn()
const replace = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  usePathname: () => "/intake",
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

function projectBody() {
  const now = new Date().toISOString()
  return {
    project_id: "p-1",
    workspace_id: "ws",
    title: "Testprojekt",
    description: "Idee",
    funding_instrument_profile_id: "f",
    data_classification: {
      sensitivity: "public",
      origin: "synthetic",
      processing_mode: "cloud_assisted",
      web_research_mode: "validated_public",
      nda_applies: false,
    },
    status: "draft",
    created_at: now,
    updated_at: now,
    active_run_id: null,
  }
}

async function fillAndSubmitIntake(partnerNames: string[]) {
  fireEvent.click(screen.getByText("Öffentlich"))
  fireEvent.change(screen.getByLabelText(/Antragstitel/), {
    target: { value: "Testprojekt" },
  })
  // R3.3: die Startoption «Mit Projektidee starten» trägt ebenfalls ein
  // Label mit «Projektidee» — die Texteingabe eindeutig über die Rolle holen.
  fireEvent.change(screen.getByRole("textbox", { name: /Projektidee/ }), {
    target: { value: "Eine Projektidee." },
  })
  for (const [index, name] of partnerNames.entries()) {
    fireEvent.click(screen.getByRole("button", { name: "Partner hinzufügen" }))
    const inputs = screen.getAllByLabelText("Partnername")
    fireEvent.change(inputs[index], { target: { value: name } })
  }
  fireEvent.click(screen.getByRole("button", { name: "Antrag anlegen" }))
}

describe("intake partner persistence (live mode)", () => {
  beforeEach(() => {
    push.mockReset()
    replace.mockReset()
    window.sessionStorage.clear()
    server.use(
      http.get("/api/session", () => HttpResponse.json(SESSION)),
      http.post("/api/projects", () =>
        HttpResponse.json(projectBody(), { status: 201 })
      )
    )
  })
  afterEach(() => setBackendMode("mock"))

  it("creates one partner per non-empty intake partner", async () => {
    const partnerPayloads: Array<Record<string, unknown>> = []
    server.use(
      http.post("/api/projects/p-1/partners", async ({ request }) => {
        partnerPayloads.push((await request.json()) as Record<string, unknown>)
        return HttpResponse.json(
          { partner_id: `pa-${partnerPayloads.length}`, project_id: "p-1" },
          { status: 201 }
        )
      })
    )
    render(
      <AppProviders mode="live">
        <IntakeForm />
      </AppProviders>
    )
    // Two named partners + one left empty → exactly two POSTs.
    await fillAndSubmitIntake(["ETH Zürich", "Industrie AG", ""])

    await waitFor(() => expect(push).toHaveBeenCalledWith("/quellen"))
    expect(partnerPayloads).toHaveLength(2)
    expect(partnerPayloads[0]).toMatchObject({
      name: "ETH Zürich",
      partner_type: "research_partner",
    })
    expect(partnerPayloads[1]).toMatchObject({
      name: "Industrie AG",
      partner_type: "research_partner",
    })
  })

  it("keeps the project and routes to /partner with a hint when partner save fails", async () => {
    server.use(
      http.post("/api/projects/p-1/partners", () =>
        HttpResponse.json({ code: "error" }, { status: 500 })
      )
    )
    render(
      <AppProviders mode="live">
        <IntakeForm />
      </AppProviders>
    )
    await fillAndSubmitIntake(["ETH Zürich"])

    await waitFor(() => expect(push).toHaveBeenCalledWith("/partner"))
    expect(push).not.toHaveBeenCalledWith("/quellen")
    expect(window.sessionStorage.getItem(PARTNER_SAVE_HINT_KEY)).toBe("1")
  })
})
