// DEMO.1 — Antragsentwurf view tests (MSW, no real backend, no provider calls).

import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { DraftPackageView } from "@/components/antragsentwurf/draft-package-view"
import { RealRunArtifacts } from "@/components/antragsentwurf/real-run-artifacts"

const CANARY = "DEMO1_UI_CANARY_7Q"

function field(
  id: string,
  label: string,
  status: string,
  overrides: Record<string, unknown> = {}
) {
  return {
    field_id: id,
    field_label: label,
    status,
    suggestion_text: status === "failed" ? null : `Entwurfstext für ${label}.`,
    missing_inputs:
      status === "missing_inputs" ? [{ label: "Englischer Antragstitel" }] : [],
    provider: status === "generated" ? "fake" : null,
    model: status === "generated" ? "fake-model" : null,
    input_tokens: status === "generated" ? 10 : null,
    output_tokens: status === "generated" ? 20 : null,
    total_tokens: status === "generated" ? 30 : null,
    latency_ms: status === "generated" ? 12 : null,
    cost_status: status === "generated" ? "not_applicable" : null,
    human_review_required: true,
    ...overrides,
  }
}

function demoPackage() {
  return {
    package_id: "dpkg-1",
    case_id: "F1-DEMO",
    created_at: "2026-07-10T00:00:00+00:00",
    provider_mode: "fake",
    data_mode: "fake_test",
    fields: [
      field("INTRO.APP.NAME", "Application name", "deterministic"),
      field("INTRO.APP.NAME_EN", "Application Name in English", "missing_inputs", {
        suggestion_text: null,
      }),
      field("INTRO.APP.ABSTRACT", "Abstract", "generated"),
      field("INTRO.APP.EXECUTIVE_SUMMARY", "Executive Summary", "generated"),
      field(
        "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS",
        "Explanations and comments",
        "generated"
      ),
      field("VC.BUSINESS_TARGETS_MODEL.EDITOR", "Business targets", "generated"),
      field("SOL.INNOVATION_SOLUTION.EDITOR", "Innovation solution", "generated"),
      field("PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION", "Explanation", "generated"),
    ],
    usage_summary: {
      input_tokens: 60,
      output_tokens: 120,
      total_tokens: 180,
      usage_record_count: 6,
      cost_status_counts: { not_applicable: 6 },
    },
    research_summary: {
      market: { used: true, candidates: 1, imported_sources: 0 },
      partner: { used: true, candidates: 1, imported_sources: 0 },
    },
    human_review_required: true,
  }
}

function mockDemoPost(body: unknown = demoPackage(), status = 200) {
  server.use(
    http.post("/api/demo/integrated-draft", () =>
      HttpResponse.json(body as Record<string, unknown>, { status })
    )
  )
}

async function generate() {
  render(<DraftPackageView />)
  fireEvent.click(screen.getByRole("button", { name: /Antragsentwurf erstellen/ }))
  await screen.findByTestId("draft-summary")
}

describe("DraftPackageView", () => {
  it("shows header, human-review hint and the generate action", () => {
    render(<DraftPackageView />)
    expect(screen.getByText("KI-gestützter Antragsentwurf")).toBeInTheDocument()
    expect(
      screen.getByText(/nicht automatisch einreichungsbereit und benötigt Human Review/)
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /Antragsentwurf erstellen/ })
    ).toBeInTheDocument()
  })

  it("shows summary cards, quality hint and copy-all warning after generating", async () => {
    mockDemoPost()
    await generate()
    const summary = screen.getByTestId("draft-summary")
    expect(summary).toHaveTextContent("Felder gesamt")
    expect(summary).toHaveTextContent("8")
    expect(summary).toHaveTextContent("Tokens gesamt")
    expect(summary).toHaveTextContent("180")
    expect(summary).toHaveTextContent("Ohne Kosten (Demo)")
    expect(summary).toHaveTextContent("Fake/Demo")
    expect(
      screen.getByText("Qualitätsbewertung durch Reviewer ausstehend.")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /Gesamten Entwurf kopieren/ })
    ).toBeInTheDocument()
    expect(
      screen.getByText("Copy-Paste ist Arbeitsentwurf, keine finale Freigabe.")
    ).toBeInTheDocument()
  })

  it("renders field cards with status, draft text, missing inputs and copy buttons", async () => {
    mockDemoPost()
    await generate()
    const abstract = screen.getByTestId("draft-field-INTRO.APP.ABSTRACT")
    expect(abstract).toHaveTextContent("KI-Vorschlag erstellt")
    expect(abstract).toHaveTextContent("Entwurfstext für Abstract.")
    expect(abstract).toHaveTextContent("Prüfung nötig")
    const nameEn = screen.getByTestId("draft-field-INTRO.APP.NAME_EN")
    expect(nameEn).toHaveTextContent("Angaben fehlen")
    expect(nameEn).toHaveTextContent("Fehlende Angaben")
    expect(nameEn).toHaveTextContent("Englischer Antragstitel")
    expect(screen.getAllByRole("button", { name: "Text kopieren" }).length).toBe(8)
  })

  it("shows the research hint on VC/SOL cards", async () => {
    mockDemoPost()
    await generate()
    const vc = screen.getByTestId("draft-field-VC.BUSINESS_TARGETS_MODEL.EDITOR")
    expect(vc).toHaveTextContent("Marktkontext genutzt: ja")
    expect(vc).toHaveTextContent("Research-Kandidaten sind keine bestätigten Fakten.")
    const sol = screen.getByTestId("draft-field-SOL.INNOVATION_SOLUTION.EDITOR")
    expect(sol).toHaveTextContent("Partnerkontext genutzt: ja")
  })

  it("keeps technical details collapsed and reveals tokens on expand", async () => {
    mockDemoPost()
    await generate()
    const abstract = screen.getByTestId("draft-field-INTRO.APP.ABSTRACT")
    expect(abstract).not.toHaveTextContent("fake-model")
    fireEvent.click(within(abstract).getByText("Technische Details"))
    await waitFor(() => expect(abstract).toHaveTextContent("fake-model"))
    expect(abstract).toHaveTextContent("10/20/30")
    expect(abstract).toHaveTextContent("INTRO.APP.ABSTRACT")
  })

  it("shows a friendly error with retry when the demo mode is off (503)", async () => {
    mockDemoPost({ code: "ai_unavailable" }, 503)
    render(<DraftPackageView />)
    fireEvent.click(screen.getByRole("button", { name: /Antragsentwurf erstellen/ }))
    expect(
      await screen.findByText("Der Demo-Modus ist auf dem Server nicht aktiviert.")
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Erneut versuchen/ })).toBeInTheDocument()
  })
})

describe("RealRunArtifacts", () => {
  it("shows the empty state when no artifacts exist (no error)", async () => {
    server.use(
      http.get("/api/demo/integrated-draft/real", () =>
        HttpResponse.json({ providers: {} })
      )
    )
    render(<RealRunArtifacts />)
    expect(
      await screen.findByText(
        "Noch kein Real-Provider-Lauf vorhanden. Führe den manuellen R5.9-REAL-Runner aus."
      )
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Es werden keine neuen Provider-Calls ausgeführt/)
    ).toBeInTheDocument()
  })

  it("renders provider cards with tokens/status/preview and never leaks raw parts", async () => {
    server.use(
      http.get("/api/demo/integrated-draft/real", () =>
        HttpResponse.json({
          providers: {
            openai: {
              provider: "openai",
              data_mode: "synthetic_eval",
              created_at: "2026-07-10T00:00:00+00:00",
              fields: [
                {
                  field_id: "INTRO.APP.ABSTRACT",
                  status: "missing_inputs",
                  provider: "openai_direct",
                  model: "gpt-x",
                  input_tokens: 1808,
                  output_tokens: 187,
                  total_tokens: 1995,
                  latency_ms: 4937,
                  cost_status: "unknown_price",
                  missing_inputs_count: 1,
                  human_review_required: true,
                  suggestion_preview: "Kurzvorschau des echten Feldentwurfs.",
                },
              ],
              usage_summary: {
                input_tokens: 1808,
                output_tokens: 187,
                total_tokens: 1995,
                usage_record_count: 1,
                cost_status_counts: { unknown_price: 1 },
              },
              // Nicht-Whitelist-Schlüssel dürfen nie gerendert werden.
              artifact: { raw_outputs: [CANARY], api_key: CANARY },
            },
          },
        })
      )
    )
    render(<RealRunArtifacts />)
    const card = await screen.findByTestId("real-run-openai")
    expect(card).toHaveTextContent("Provider: openai")
    expect(card).toHaveTextContent("synthetic_eval")
    expect(card).toHaveTextContent("gpt-x")
    expect(card).toHaveTextContent("1808/187/1995")
    expect(card).toHaveTextContent("Preis unbekannt")
    expect(card).toHaveTextContent("Kurzvorschau des echten Feldentwurfs.")
    expect(document.body.textContent).not.toContain(CANARY)
    expect(document.body.textContent).not.toContain("api_key")
  })
})
