import { describe, it, expect } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { LiveRequirements } from "@/components/anforderungen/live-requirements"

function assessment(overrides: Record<string, unknown> = {}) {
  return {
    assessment_id: "as1",
    requirement_id: "REQ.INNO.PARTNER.IMPLEMENTATION",
    title: "Umsetzungspartner vorhanden",
    status: "partial",
    basis: "deterministic_rule",
    reasoning: "Teilweise erfüllt.",
    stale: false,
    evidence_links: [],
    open_issues: [],
    ...overrides,
  }
}

const activeLink = {
  evidence_link_id: "l1",
  anchor_id: "an42",
  target_type: "requirement_assessment",
  target_id: "as1",
  status: "active",
  created_at: new Date().toISOString(),
}

describe("LiveRequirements actions (M10.2)", () => {
  it("links 'Beleg ansehen' to the evidence deep link when evidence exists", async () => {
    server.use(
      http.get("/api/runs/r1/requirements", () =>
        HttpResponse.json([assessment({ evidence_links: [activeLink] })])
      )
    )
    render(<LiveRequirements runId="r1" />)
    const rowToggle = await screen.findByRole("button", {
      name: /Umsetzungspartner vorhanden/,
    })
    fireEvent.click(rowToggle)

    // Rendered as <a role="button"> (Base UI render prop) — assert the href.
    const evidenceLink = await screen.findByRole("button", { name: "Beleg ansehen" })
    expect(evidenceLink).toHaveAttribute(
      "href",
      "/anforderungen?tab=evidenz&anchor=an42"
    )
    // Partner requirement → primary CTA routes to the intake partner section.
    expect(
      screen.getByRole("button", { name: "Im Intake Partner ergänzen" })
    ).toHaveAttribute("href", "/intake")
    // Guidance-only human review: neutral link into the Qualitätsprüfung.
    expect(
      screen.getByRole("button", { name: "In Qualitätsprüfung öffnen" })
    ).toHaveAttribute("href", "/review")
    // The old generic buttons are gone.
    expect(screen.queryByRole("button", { name: "In Review übernehmen" })).toBeNull()
    expect(
      screen.queryByRole("button", { name: "Kommentar im Review erfassen" })
    ).toBeNull()
  })

  it("offers 'Quelle ergänzen' when no evidence is linked", async () => {
    server.use(
      http.get("/api/runs/r1/requirements", () =>
        HttpResponse.json([
          assessment({
            assessment_id: "as2",
            title: "Forschungspartner beitragsberechtigt",
            status: "blocked",
          }),
        ])
      )
    )
    render(<LiveRequirements runId="r1" />)
    const rowToggle = await screen.findByRole("button", {
      name: /Forschungspartner beitragsberechtigt/,
    })
    fireEvent.click(rowToggle)

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Quelle ergänzen" })
      ).toHaveAttribute("href", "/quellen")
    )
    expect(screen.queryByRole("button", { name: "Beleg ansehen" })).toBeNull()
  })
})
