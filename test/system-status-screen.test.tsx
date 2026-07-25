import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { SystemStatusScreen } from "@/components/system-status/system-status-screen"
import { getSystemStatus, runConnectionCheck } from "@/lib/system-status"

vi.mock("@/lib/system-status", async () => {
  const actual = await vi.importActual<typeof import("@/lib/system-status")>("@/lib/system-status")
  return { ...actual, getSystemStatus: vi.fn(), runConnectionCheck: vi.fn() }
})

const mockedGetStatus = vi.mocked(getSystemStatus)
const mockedRunCheck = vi.mocked(runConnectionCheck)

const memberStatus = {
  services: [
    { id: "ai" as const, label: "KI-Vorschläge", state: "available" as const, message: "KI-Vorschläge können verwendet werden.", next_step: "Keine Aktion nötig.", checked_at: "2026-07-24T08:00:00Z" },
    { id: "web" as const, label: "Webrecherche", state: "attention" as const, message: "Die Webrecherche ist konfiguriert, aber noch nicht geprüft.", next_step: "Ein Lead-Admin kann die Verbindung mit Testdaten prüfen.", checked_at: null },
  ],
  can_run_connection_check: false,
}

describe("SystemStatusScreen", () => {
  beforeEach(() => {
    mockedGetStatus.mockResolvedValue(memberStatus)
    mockedRunCheck.mockResolvedValue({ ...memberStatus, can_run_connection_check: true })
  })

  it("zeigt allen Mitgliedern kompakte Dienstestatus ohne Rollen- oder Modelltabelle", async () => {
    render(<SystemStatusScreen />)
    expect(await screen.findByRole("heading", { level: 1, name: "Systemstatus" })).toBeInTheDocument()
    expect(screen.getByText("KI-Vorschläge")).toBeInTheDocument()
    expect(screen.getByText("Webrecherche")).toBeInTheDocument()
    expect(screen.getAllByText(/Ein Lead-Admin kann die Verbindung/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/A1_FACT|GPT-5\.6|Provider/)).toBeNull()
  })

  it("bietet Lead-Admins den verständlichen Testknopf", async () => {
    mockedGetStatus.mockResolvedValue({ ...memberStatus, can_run_connection_check: true })
    render(<SystemStatusScreen />)
    const button = await screen.findByRole("button", { name: "Verbindung mit Testdaten prüfen" })
    fireEvent.click(button)
    await waitFor(() => expect(mockedRunCheck).toHaveBeenCalledTimes(1))
  })
})
