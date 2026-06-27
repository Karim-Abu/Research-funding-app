import { describe, it, expect } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { LiveEvidence } from "@/components/quellen/live-evidence"

function anchor(overrides: Record<string, unknown> = {}) {
  return {
    anchor_id: "an1",
    source_version_id: "sv1",
    fragment_id: "f1",
    quote: "Müller prüft die Förderfähigkeit für größere Vorhaben.",
    verification_status: "exact_verified",
    source_id: "s1",
    source_name: "Quelle.txt",
    source_type: "txt",
    normalizer_version: "normalizer-1",
    page: 2,
    section: null,
    match_type: "exact_normalized",
    human_checked_by: null,
    human_checked_at: null,
    start_offset: 0,
    end_offset: 50,
    match_score: null,
    coverage: null,
    source_accessed_at: null,
    ...overrides,
  }
}

function assessment(links: unknown[]) {
  return {
    assessment_id: "as1",
    requirement_id: "REQ.X",
    title: "Förderfähigkeit prüfen",
    status: "partial",
    basis: "hybrid",
    reasoning: "…",
    stale: false,
    evidence_links: links,
    open_issues: [],
  }
}

function link() {
  return {
    evidence_link_id: "l1",
    anchor_id: "an1",
    target_type: "requirement_assessment",
    target_id: "as1",
    status: "active",
    created_at: new Date().toISOString(),
  }
}

function mock(anchors: unknown[], assessments: unknown[]) {
  server.use(
    http.get("/api/runs/r1/evidence", () => HttpResponse.json(anchors)),
    http.get("/api/runs/r1/requirements", () => HttpResponse.json(assessments))
  )
}

describe("LiveEvidence", () => {
  it("renders a verified Unicode quote with joined requirement context", async () => {
    mock([anchor()], [assessment([link()])])
    render(<LiveEvidence runId="r1" />)
    await waitFor(() =>
      expect(
        screen.getByText("Müller prüft die Förderfähigkeit für größere Vorhaben.")
      ).toBeInTheDocument()
    )
    expect(screen.getByText("Fundstelle bestätigt")).toBeInTheDocument()
    expect(screen.getByText(/Förderfähigkeit prüfen/)).toBeInTheDocument()
    // No human-check / "Geprüft von" controls in M5.
    expect(screen.queryByText(/Geprüft von/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Menschlich geprüft/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Als geprüft markieren/)).not.toBeInTheDocument()
  })

  it("renders rejected/unverified labels distinctly", async () => {
    mock(
      [
        anchor({ anchor_id: "a-un", verification_status: "unverified", quote: "Offen." }),
        anchor({ anchor_id: "a-rej", verification_status: "rejected", quote: "Abgelehnt." }),
      ],
      [assessment([])]
    )
    render(<LiveEvidence runId="r1" />)
    await waitFor(() => expect(screen.getByText("Offen.")).toBeInTheDocument())
    expect(screen.getByText("Prüfen")).toBeInTheDocument()
    expect(screen.getByText("Nicht bestätigt")).toBeInTheDocument()
    // Verified-coverage indicator counts only exact_verified (here: 0).
    expect(screen.getByText(/0 bestätigte Fundstelle/)).toBeInTheDocument()
  })

  it("shows a calm empty state when there is no evidence", async () => {
    mock([], [])
    render(<LiveEvidence runId="r1" />)
    await waitFor(() =>
      expect(screen.getByText(/Noch keine Belege/)).toBeInTheDocument()
    )
  })
})
