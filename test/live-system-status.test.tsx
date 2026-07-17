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
})
