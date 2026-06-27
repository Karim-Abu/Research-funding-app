import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"
import {
  listRequirements,
  STATUS_LABELS,
  STALE_NOTICE,
} from "@/lib/requirements"

function assessmentDoc(overrides: Record<string, unknown> = {}) {
  return {
    assessment_id: "a1",
    requirement_id: "REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH",
    title: "Umsetzungspartner mit Schweiz-Bezug",
    status: "partial",
    basis: "hybrid",
    reasoning: "1 passende(r) Partner vorhanden.",
    stale: false,
    evidence_links: [],
    open_issues: [],
    ...overrides,
  }
}

describe("requirements client (live)", () => {
  beforeEach(() => setBackendMode("live"))
  afterEach(() => setBackendMode("mock"))

  it("parses run-scoped assessments", async () => {
    server.use(
      http.get("/api/runs/r1/requirements", () =>
        HttpResponse.json([
          assessmentDoc(),
          assessmentDoc({ assessment_id: "a2", status: "blocked", basis: "hybrid" }),
        ])
      )
    )
    const items = await listRequirements("r1")
    expect(items).toHaveLength(2)
    expect(items[0].status).toBe("partial")
    expect(items[1].status).toBe("blocked")
  })

  it("surfaces staleness flag from the contract", async () => {
    server.use(
      http.get("/api/runs/r2/requirements", () =>
        HttpResponse.json([assessmentDoc({ stale: true })])
      )
    )
    const items = await listRequirements("r2")
    expect(items.some((a) => a.stale)).toBe(true)
  })

  it("404 → user-safe error", async () => {
    server.use(
      http.get("/api/runs/missing/requirements", () =>
        HttpResponse.json({ code: "not_found" }, { status: 404 })
      )
    )
    await expect(listRequirements("missing")).rejects.toThrow("nicht gefunden")
  })

  it("exposes German status labels + stale notice", () => {
    expect(STATUS_LABELS.fulfilled).toBe("Erfüllt")
    expect(STATUS_LABELS.needs_input).toBe("Angaben nötig")
    expect(STATUS_LABELS.blocked).toBe("Blockiert")
    expect(STALE_NOTICE).toContain("erneut")
  })
})
