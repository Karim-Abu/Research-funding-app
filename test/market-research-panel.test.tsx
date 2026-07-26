import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { http, HttpResponse } from "msw"

import { MarketResearchPanel } from "@/components/editor/market-research-panel"
import { server } from "./server"

describe("MarketResearchPanel", () => {
  it("uses the same persistent research workspace as the sources view", async () => {
    server.use(
      http.get("/api/projects/p1/research-workspace", () => HttpResponse.json({
        brief: { latest: null, active_approved: null },
        queries: [], results: [], provider_mode: "unavailable",
      })),
    )
    render(<MarketResearchPanel projectId="p1" />)
    expect(await screen.findByTestId("public-research-panel")).toBeInTheDocument()
    // Der Editor-Wrapper trägt keinen eigenen Erklärsatz mehr — das Panel
    // bringt seinen Kopf samt Datenschutzregel selbst mit (UI-Bereinigung R1).
    expect(
      screen.getByText(/Keine Rohprojektidee, Partnernamen, Budgets oder Kontaktangaben/)
    ).toBeInTheDocument()
    expect(screen.queryByLabelText(/Anwendungsbereich/)).toBeNull()
  })

  it("does not expose the legacy client-side market simulation", async () => {
    server.use(
      http.get("/api/projects/p1/research-workspace", () => HttpResponse.json({
        brief: { latest: null, active_approved: null },
        queries: [], results: [], provider_mode: "fake_demo",
      })),
    )
    render(<MarketResearchPanel projectId="p1" />)
    expect(await screen.findByText(/Recherchebrief vorschlagen/)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Marktanalyse vorbereiten" })).toBeNull()
  })
})
