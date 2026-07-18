import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { LiveSystemStatus } from "@/components/admin/live-system-status"
import {
  getLiveSystemStatus,
  type LiveSystemStatusDto,
} from "@/lib/live-system-status"

vi.mock("@/lib/live-system-status", async () => {
  const actual = await vi.importActual<typeof import("@/lib/live-system-status")>(
    "@/lib/live-system-status"
  )
  return {
    ...actual,
    getLiveSystemStatus: vi.fn(),
    runLiveSystemPreflight: vi.fn(),
  }
})

const mockedStatus = vi.mocked(getLiveSystemStatus)

function status(
  generation_mode: LiveSystemStatusDto["generation_mode"],
  generation_unavailable_reason: string | null = null
): LiveSystemStatusDto {
  return {
    overall_status: generation_mode === "real_eval" ? "available" : "unavailable",
    registry_version: "test-registry",
    generation_mode,
    generation_unavailable_reason,
    routes: [],
    firecrawl: {
      mode: "disabled",
      available: false,
      preflight_status: "not_run",
      checks: [],
    },
  }
}

describe("LiveSystemStatus", () => {
  beforeEach(() => mockedStatus.mockReset())

  it("kennzeichnet Live-KI eindeutig und nie gleichzeitig als Demo", async () => {
    mockedStatus.mockResolvedValue(status("real_eval"))
    render(<LiveSystemStatus />)
    expect(await screen.findByText("Live-KI verfügbar")).toBeInTheDocument()
    expect(screen.queryByText(/^Demo$/)).toBeNull()
  })

  it("zeigt bei Live-Konflikt die konkrete nächste Aktion", async () => {
    mockedStatus.mockResolvedValue(
      status("live_unavailable", "live_fake_conflict")
    )
    render(<LiveSystemStatus />)
    expect((await screen.findAllByText("Nicht verfügbar")).length).toBeGreaterThan(0)
    expect(
      screen.getByText(/Setzen Sie AGENT_FAKE_PROVIDER=false/)
    ).toBeInTheDocument()
    expect(screen.queryByText(/^Demo$/)).toBeNull()
  })

  it("zeigt je Route und für Firecrawl den Zeitpunkt des letzten Preflights", async () => {
    const dto = status("real_eval")
    dto.routes = [{
      role_id: "A2_INNOSUISSE_PROPOSAL_WRITER",
      route_key: "openai_gpt_56_terra_candidate",
      route_alias: "gpt-5.6-terra",
      provider: "openai_direct",
      requested_model_id: "gpt-5.6-terra-2026",
      actual_model_id: "gpt-5.6-terra-2026",
      configuration_status: "configured",
      preflight_status: "pass",
      checked_at: "2026-07-17T08:30:00Z",
      expires_at: "2026-07-17T14:30:00Z",
      capabilities: {},
      cost_status: "priced",
      checks: [],
    }]
    dto.firecrawl = {
      mode: "live", available: true, preflight_status: "pass",
      checked_at: "2026-07-17T08:31:00Z", checks: [],
    }
    mockedStatus.mockResolvedValue(dto)
    render(<LiveSystemStatus />)
    expect(await screen.findByText("Zuletzt geprüft")).toBeInTheDocument()
    // Route-Zeile: Zeitstempel + Gültigkeit; Firecrawl: eigener Zeitstempel.
    expect(screen.getByText(/gültig bis/)).toBeInTheDocument()
    expect(screen.getByText(/Zuletzt geprüft: /)).toBeInTheDocument()
    expect(screen.queryByText(/^—$/)).toBeNull()
  })
})
