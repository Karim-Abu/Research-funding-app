// R1.3 — Kanonische Statusanzeige: eine Quelle (lib/status.ts), ein Badge.
import { describe, it, expect } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { CanonicalStatusBadge } from "@/components/status/canonical-status"

function statusDto(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "r1",
    blocker_count: 18,
    warning_count: 54,
    human_review_count: 4,
    stale: false,
    approval_status: "blocked",
    review_package_version: "rpv-abc",
    per_area_counts: { INTRO: 4, VC: 7 },
    last_reviewed_at: null,
    ...overrides,
  }
}

describe("CanonicalStatusBadge", () => {
  it("zeigt die kanonische Blocker-Zahl aus dem Status-View", async () => {
    server.use(
      http.get("/api/runs/r1/review/status", () =>
        HttpResponse.json(statusDto())
      )
    )
    render(<CanonicalStatusBadge runId="r1" />)
    await waitFor(() =>
      expect(screen.getByTestId("canonical-blocker-count")).toHaveTextContent(
        "18 Blocker offen"
      )
    )
    expect(
      screen.getByTestId("canonical-blocker-count").getAttribute(
        "data-blocker-count"
      )
    ).toBe("18")
    expect(screen.queryByTestId("canonical-stale")).not.toBeInTheDocument()
  })

  it("zeigt bei stale den einheitlichen Wortlaut «Prüfung nicht aktuell»", async () => {
    server.use(
      http.get("/api/runs/r1/review/status", () =>
        HttpResponse.json(statusDto({ stale: true }))
      )
    )
    render(<CanonicalStatusBadge runId="r1" />)
    await waitFor(() =>
      expect(screen.getByTestId("canonical-stale")).toHaveTextContent(
        "Prüfung nicht aktuell"
      )
    )
  })

  it("zeigt 0 Blocker positiv formuliert («Keine Blocker offen»)", async () => {
    server.use(
      http.get("/api/runs/r1/review/status", () =>
        HttpResponse.json(statusDto({ blocker_count: 0 }))
      )
    )
    render(<CanonicalStatusBadge runId="r1" />)
    await waitFor(() =>
      expect(screen.getByTestId("canonical-blocker-count")).toHaveTextContent(
        "Keine Blocker offen"
      )
    )
  })

  it("Parität: zwei Einbettungen desselben Runs zeigen dieselbe Zahl", async () => {
    server.use(
      http.get("/api/runs/r1/review/status", () =>
        HttpResponse.json(statusDto({ blocker_count: 7 }))
      )
    )
    render(
      <>
        <CanonicalStatusBadge runId="r1" />
        <CanonicalStatusBadge runId="r1" />
      </>
    )
    await waitFor(() =>
      expect(screen.getAllByTestId("canonical-blocker-count")).toHaveLength(2)
    )
    const counts = screen
      .getAllByTestId("canonical-blocker-count")
      .map((el) => el.getAttribute("data-blocker-count"))
    expect(counts).toEqual(["7", "7"])
  })
})
