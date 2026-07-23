import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { QualitySummary } from "@/components/review/quality-summary"

const RUN = "run-1"

function view(overrides: Record<string, unknown> = {}) {
  return {
    run_id: RUN,
    available: true,
    reliability_stale: false,
    summary: {
      summary_id: "rqs-1",
      run_id: RUN,
      status: "current",
      stale: false,
      quality_flag: "risky",
      claim_count: 3,
      supported_claims: 1,
      weakly_supported_claims: 1,
      unsupported_claims: 1,
      conflicting_claims: 0,
      evidence_coverage: 0.66,
      evidence_correctness_sample_size: 2,
      evidence_correctness_sample_pass_rate: 0.5,
      review_required_count: 2,
      blocker_count: 1,
      warning_count: 1,
      fields_ready: 0,
      fields_needs_review: 1,
      false_consensus_risk_count: 0,
      semantic_drift_count: 0,
      raw_logging_detected: false,
      tool_leakage_detected: false,
      summary_version: "run-quality-1",
      generated_at: new Date().toISOString(),
    },
    claims: [],
    findings: [
      {
        finding_id: "f1",
        field_id: "SOL.INNOVATION_SOLUTION.EDITOR",
        severity: "blocker",
        description: "Nicht belegte Aussage: keine verknüpfte Quelle gefunden.",
        status: "open",
        finding_code: "reliability:unsupported:clm-1",
        target_type: "draft_claim",
        target_id: "clm-1",
      },
    ],
    ...overrides,
  }
}

describe("QualitySummary", () => {
  it("renders metrics, the risk flag and reliability blockers", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/reliability`, () => HttpResponse.json(view()))
    )
    render(<QualitySummary runId={RUN} />)
    await waitFor(() =>
      expect(screen.getByTestId("quality-metrics")).toBeInTheDocument()
    )
    expect(screen.getByText("Qualitätsrisiko")).toBeInTheDocument()
    expect(screen.getByTestId("reliability-blockers")).toHaveTextContent(
      /Nicht belegte Aussage/
    )
    // M10.2: coverage ≠ sufficiency + "risky is a signal, not an app failure".
    expect(
      screen.getByText(/Abdeckung .*nicht dasselbe wie Suffizienz/)
    ).toBeInTheDocument()
    expect(screen.getByText(/kein Fehler der Anwendung/)).toBeInTheDocument()
    // No provider/model/confidence-percentage leakage.
    expect(
      screen.queryByText(/anthropic|haiku|firecrawl|confidence|Konfidenz|%/i)
    ).toBeNull()
  })

  it("RUN 4A: Reliability-Jargon liegt nur in den aufklappbaren Audit-Details", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/reliability`, () => HttpResponse.json(view()))
    )
    render(<QualitySummary runId={RUN} />)
    await waitFor(() =>
      expect(screen.getByTestId("quality-metrics")).toBeInTheDocument()
    )
    const details = screen.getByTestId("quality-audit-details")
    expect(details.tagName).toBe("DETAILS")
    // Fachbegriffe sind im DOM (verlagert, nicht gelöscht), aber im
    // zugeklappten <details> nicht sichtbar.
    expect(screen.getByText(/Falsches Konsensrisiko/)).not.toBeVisible()
    expect(screen.getByText(/Semantische Drift/)).not.toBeVisible()
    expect(screen.getByText(/Beleg-Suffizienzprüfung/)).not.toBeVisible()
    // Der Klartextsatz bleibt im Standardfluss sichtbar.
    expect(
      screen.getByText(/Risikosignal für die menschliche Prüfung/)
    ).toBeVisible()
  })

  it("shows an empty state and runs a pass on demand", async () => {
    let done = false
    server.use(
      http.get(`/api/runs/${RUN}/reliability`, () =>
        HttpResponse.json(
          done
            ? view()
            : { run_id: RUN, available: false, reliability_stale: false, summary: null, claims: [], findings: [] }
        )
      ),
      http.post(`/api/runs/${RUN}/reliability`, () =>
        HttpResponse.json(
          { operation_id: "op-1", resource_type: "reliability", resource_id: RUN, status: "queued", poll_url: "/api/v1/operations/op-1" },
          { status: 202 }
        )
      ),
      http.get("/api/operations/op-1", () => {
        done = true
        return HttpResponse.json({
          operation_id: "op-1",
          resource_type: "reliability",
          resource_id: RUN,
          status: "succeeded",
          created_at: new Date().toISOString(),
        })
      })
    )
    render(<QualitySummary runId={RUN} />)
    await waitFor(() =>
      expect(screen.getByText(/Noch keine Zuverlässigkeitsprüfung/)).toBeInTheDocument()
    )
    fireEvent.click(screen.getByRole("button", { name: /Zuverlässigkeit prüfen/ }))
    await waitFor(() =>
      expect(screen.getByTestId("quality-metrics")).toBeInTheDocument()
    )
  })
})
