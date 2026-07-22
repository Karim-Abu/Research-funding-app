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

describe("LiveRequirements — Compliance ≠ Human Review (RUN 2A Slice 1)", () => {
  it("zeigt einen erfüllten Hybrid-Check als Erfüllt mit offener Bestätigung, nie als Teilweise erfüllt", async () => {
    server.use(
      http.get("/api/runs/r1/requirements", () =>
        HttpResponse.json([
          assessment({
            assessment_id: "as-share",
            requirement_id: "REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60",
            title: "Umsetzungspartner-Beitrag 40–60 %",
            status: "fulfilled",
            basis: "hybrid",
            reasoning: "Beitrag 52% liegt im Band 40–60%.",
            review_status: "required",
            display_mode: "requirement",
          }),
        ])
      )
    )
    render(<LiveRequirements runId="r1" />)
    const rowToggle = await screen.findByRole("button", {
      name: /Umsetzungspartner-Beitrag/,
    })

    // Primärstatus = Compliance; Sekundärbadge = Reviewzustand — die Zeile
    // selbst zeigt nie «Teilweise erfüllt» für eine bestandene Mathematikregel.
    expect(rowToggle).toHaveTextContent(
      "Maschinell geprüft · Bestätigung offen"
    )
    expect(rowToggle).not.toHaveTextContent("Teilweise erfüllt")
    // Gruppenzähler: der erfüllte Hybrid-Check zählt als erfüllt.
    expect(screen.getByText("1 / 1 erfüllt")).toBeInTheDocument()
  })

  it("bestätigte Prüfung zeigt Menschlich bestätigt und keine offene Markierung", async () => {
    server.use(
      http.get("/api/runs/r1/requirements", () =>
        HttpResponse.json([
          assessment({
            assessment_id: "as-cash",
            requirement_id: "REQ.INNO.BUDGET.CASH_MIN5",
            title: "Barbeitrag mindestens 5 %",
            status: "fulfilled",
            basis: "hybrid",
            reasoning: "Barbeitrag 5% erfüllt das Minimum.",
            review_status: "confirmed",
            display_mode: "requirement",
          }),
        ])
      )
    )
    render(<LiveRequirements runId="r1" />)
    const rowToggle = await screen.findByRole("button", {
      name: /Barbeitrag mindestens/,
    })
    expect(
      screen.queryByText("Maschinell geprüft · Bestätigung offen")
    ).toBeNull()
    fireEvent.click(rowToggle)
    expect(await screen.findByText("Menschlich bestätigt")).toBeInTheDocument()
  })

  it("RUN 4A Statussprache: open → «Prüfung nötig», blocked → «Nicht erfüllt», nie Roh-Enums", async () => {
    server.use(
      http.get("/api/runs/r1/requirements", () =>
        HttpResponse.json([
          assessment({
            assessment_id: "as-open",
            requirement_id: "REQ.INNO.SOL.INNOVATION_DESCRIBED",
            title: "Innovationsgehalt dargelegt",
            status: "open",
            basis: "semantic_assessment",
            reasoning: "Inhaltliche Prüfung durch eine Person nötig.",
          }),
          assessment({
            assessment_id: "as-blocked",
            requirement_id: "REQ.INNO.ELIG.SWISS_PARTNER",
            title: "Schweizer Forschungspartner vorhanden",
            status: "blocked",
            reasoning: "Kein beitragsberechtigter Forschungspartner erfasst.",
          }),
        ])
      )
    )
    render(<LiveRequirements runId="r1" />)
    const openRow = await screen.findByRole("button", {
      name: /Innovationsgehalt dargelegt/,
    })
    fireEvent.click(openRow)
    // Detailebene: präzises Label + Kurzbegründung, kein «Nicht erfüllt».
    expect(
      await screen.findByText(/Nicht maschinell entscheidbar/)
    ).toBeInTheDocument()

    const blockedRow = screen.getByRole("button", {
      name: /Schweizer Forschungspartner vorhanden/,
    })
    fireEvent.click(blockedRow)
    expect(await screen.findByText(/Die Regel ist verletzt/)).toBeInTheDocument()
    expect(screen.getByText("Nicht erfüllt")).toBeInTheDocument()

    // Roh-Enums erscheinen nie im Standardfluss.
    expect(screen.queryByText(/^open$/)).toBeNull()
    expect(screen.queryByText(/^blocked$/)).toBeNull()
    expect(screen.queryByText(/^needs_input$/)).toBeNull()
  })

  it("Guidance-Hinweise laufen in die Hinweise-Sektion und zählen in keiner Quote", async () => {
    server.use(
      http.get("/api/runs/r1/requirements", () =>
        HttpResponse.json([
          assessment({
            assessment_id: "as-share",
            requirement_id: "REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60",
            title: "Umsetzungspartner-Beitrag 40–60 %",
            status: "fulfilled",
            basis: "hybrid",
            reasoning: "Beitrag 52% liegt im Band 40–60%.",
            review_status: "required",
            display_mode: "requirement",
          }),
          assessment({
            assessment_id: "as-guidance",
            requirement_id: "REQ.INNO.BUDGET.NO_FINANCIAL_CAP",
            title: "Keine formale finanzielle Obergrenze",
            status: "fulfilled",
            basis: "semantic_assessment",
            reasoning: "Keine formale Obergrenze; Angabe vorhanden.",
            review_status: "not_required",
            display_mode: "guidance",
          }),
        ])
      )
    )
    render(<LiveRequirements runId="r1" />)
    await screen.findByRole("button", { name: /Umsetzungspartner-Beitrag/ })

    const notes = screen.getByTestId("guidance-notes")
    expect(notes).toHaveTextContent("Keine formale finanzielle Obergrenze")
    // Nicht in den zählenden Gruppen: die Quote bleibt 1 / 1 (ohne Guidance).
    expect(screen.getByText("1 / 1 erfüllt")).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /Keine formale finanzielle Obergrenze/ })
    ).toBeNull()
  })
})
