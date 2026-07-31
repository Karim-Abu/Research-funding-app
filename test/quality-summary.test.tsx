import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { QualitySummary } from "@/components/review/quality-summary"

const RUN = "run-1"

function finding(overrides: Record<string, unknown> = {}) {
  return {
    finding_id: "f1",
    field_id: "SOL.INNOVATION_SOLUTION.EDITOR",
    severity: "warning",
    description: "Nicht belegte Aussage: keine verknüpfte Quelle gefunden.",
    status: "open",
    finding_code: "reliability:unsupported:clm-1",
    target_type: "draft_claim",
    target_id: "clm-1",
    ...overrides,
  }
}

/** n Findings einer Familie (eigene ids, damit React-Keys stabil sind). */
function family(
  code: string,
  count: number,
  severity = "warning",
  description = "Meldung",
) {
  return Array.from({ length: count }, (_, i) =>
    finding({
      finding_id: `${code}-${i}`,
      severity,
      description,
      finding_code: `reliability:${code}:clm-${i}`,
      target_id: `clm-${i}`,
    })
  )
}

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
    findings: [finding()],
    ...overrides,
  }
}

function renderCard(onShowCheckpoints = vi.fn()) {
  render(<QualitySummary runId={RUN} onShowCheckpoints={onShowCheckpoints} />)
  return onShowCheckpoints
}

describe("QualitySummary", () => {
  it("zeigt einen Status und konkrete Prüfpunkte in Klartext", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/reliability`, () =>
        HttpResponse.json(
          view({
            findings: [
              ...family("market", 9),
              ...family("proposed_fact", 4),
              ...family("quantified", 10),
            ],
          })
        )
      )
    )
    renderCard()
    await waitFor(() =>
      expect(screen.getByTestId("quality-checkpoints")).toBeInTheDocument()
    )
    expect(screen.getByTestId("quality-status")).toHaveTextContent(
      "Prüfung erforderlich"
    )
    const list = screen.getByTestId("quality-checkpoints")
    expect(within(list).getAllByRole("listitem")).toHaveLength(3)
    expect(list).toHaveTextContent(
      "10 Zahlen stimmen noch nicht eindeutig mit den Quellen überein."
    )
    expect(list).toHaveTextContent(
      "9 Markt- und Wettbewerbsangaben brauchen einen Beleg."
    )
    expect(list).toHaveTextContent("4 KI-Vorschläge wurden noch nicht bestätigt.")
    // Ehrliche Einordnung bleibt in der Standardansicht sichtbar.
    expect(screen.getByText(/kein Fehler der Anwendung/)).toBeVisible()
    // Keine Provider-/Modell-/Konfidenz-Leaks.
    expect(
      screen.queryByText(/anthropic|haiku|firecrawl|confidence|Konfidenz|%/i)
    ).toBeNull()
  })

  it("«kritisch» nur bei Punkten, die den Export blockieren", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/reliability`, () =>
        HttpResponse.json(
          view({
            findings: [
              ...family("conflict", 1, "blocker"),
              ...family("unsupported", 20),
            ],
          })
        )
      )
    )
    renderCard()
    await waitFor(() =>
      expect(screen.getByTestId("quality-checkpoints")).toBeInTheDocument()
    )
    const items = within(screen.getByTestId("quality-checkpoints")).getAllByRole(
      "listitem"
    )
    // Kritischer Punkt steht zuerst, obwohl die andere Gruppe grösser ist.
    expect(items[0]).toHaveTextContent(
      "1 Angabe widerspricht der verknüpften Quelle."
    )
    expect(items[0]).toHaveTextContent("kritisch")
    expect(items[1]).toHaveTextContent("20 Stellen brauchen noch einen Beleg.")
    expect(items[1]).not.toHaveTextContent("kritisch")
    expect(screen.getAllByText("kritisch")).toHaveLength(1)
  })

  it("Fachbegriffe und Kennzahlen nur in den technischen Prüfinformationen", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/reliability`, () => HttpResponse.json(view()))
    )
    renderCard()
    await waitFor(() =>
      expect(screen.getByTestId("quality-checkpoints")).toBeInTheDocument()
    )
    const details = screen.getByTestId("quality-audit-details")
    expect(details.tagName).toBe("DETAILS")
    expect(
      within(details).getByText("Technische Prüfinformationen")
    ).toBeInTheDocument()
    // Verlagert, nicht gelöscht: im DOM vorhanden, zugeklappt nicht sichtbar.
    expect(screen.getByTestId("quality-metrics")).not.toBeVisible()
    expect(screen.getByText(/Falsches Konsensrisiko/)).not.toBeVisible()
    expect(screen.getByText(/Semantische Drift/)).not.toBeVisible()
    expect(screen.getByText(/Beleg-Suffizienzprüfung/)).not.toBeVisible()
    // M10.2: Abdeckung ≠ Suffizienz bleibt dokumentiert.
    expect(
      screen.getByText(/Abdeckung .*nicht dasselbe wie Suffizienz/)
    ).not.toBeVisible()
    // Der Wortlaut der Einzelmeldungen bleibt auditierbar.
    expect(
      within(screen.getByTestId("quality-findings-verbatim")).getByText(
        /Nicht belegte Aussage/
      )
    ).toBeInTheDocument()
    // «Qualitätsrisiko» erscheint nicht mehr in der Standardansicht.
    expect(screen.getByTestId("quality-status")).not.toHaveTextContent(
      "Qualitätsrisiko"
    )
  })

  it("höchstens drei Prüfpunkte; der Rest steht in den technischen Details", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/reliability`, () =>
        HttpResponse.json(
          view({
            findings: [
              ...family("unsupported", 5),
              ...family("market", 4),
              ...family("quantified", 3),
              ...family("weak", 2),
              ...family("drift", 1),
            ],
          })
        )
      )
    )
    renderCard()
    await waitFor(() =>
      expect(screen.getByTestId("quality-checkpoints")).toBeInTheDocument()
    )
    expect(
      within(screen.getByTestId("quality-checkpoints")).getAllByRole("listitem")
    ).toHaveLength(3)
    expect(screen.getByText(/und 2 weitere Prüfpunkte/)).toBeVisible()
    const overflow = screen.getByTestId("quality-checkpoints-overflow")
    expect(overflow).toHaveTextContent("Bei 2 Stellen reicht der Beleg noch nicht aus.")
    expect(overflow).toHaveTextContent("1 Formulierung sagt mehr aus als der Beleg.")
    expect(overflow).not.toBeVisible()
  })

  it("Hauptaktion «Prüfpunkte anzeigen» führt zur Aufgabenliste", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/reliability`, () => HttpResponse.json(view()))
    )
    const onShow = renderCard()
    await waitFor(() =>
      expect(screen.getByTestId("quality-checkpoints")).toBeInTheDocument()
    )
    fireEvent.click(screen.getByRole("button", { name: "Prüfpunkte anzeigen" }))
    expect(onShow).toHaveBeenCalledOnce()
  })

  it("ohne offene Prüfpunkte: grüner Status, keine Aufgabe", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/reliability`, () =>
        HttpResponse.json(view({ findings: [] }))
      )
    )
    renderCard()
    await waitFor(() =>
      expect(screen.getByTestId("quality-status")).toHaveTextContent(
        "Keine offenen Prüfpunkte"
      )
    )
    expect(screen.queryByTestId("quality-checkpoints")).toBeNull()
    expect(
      screen.queryByRole("button", { name: "Prüfpunkte anzeigen" })
    ).toBeNull()
  })

  it("veralteter Stand: erneut prüfen ist die Hauptaktion", async () => {
    server.use(
      http.get(`/api/runs/${RUN}/reliability`, () =>
        HttpResponse.json(view({ reliability_stale: true }))
      )
    )
    renderCard()
    await waitFor(() =>
      expect(screen.getByTestId("reliability-stale")).toBeInTheDocument()
    )
    expect(screen.getByRole("button", { name: /Erneut prüfen/ })).toBeVisible()
    expect(
      screen.queryByRole("button", { name: "Prüfpunkte anzeigen" })
    ).toBeNull()
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
    renderCard()
    await waitFor(() =>
      expect(screen.getByText(/noch nicht geprüft/)).toBeInTheDocument()
    )
    fireEvent.click(screen.getByRole("button", { name: /Belege jetzt prüfen/ }))
    await waitFor(() =>
      expect(screen.getByTestId("quality-checkpoints")).toBeInTheDocument()
    )
  })
})
