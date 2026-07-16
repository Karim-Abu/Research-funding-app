import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import {
  AnalysisProgressBanner,
  CompletedAnalysisBanner,
} from "@/components/quellen/analysis-progress-banner"
import { RunTechnicalDetails } from "@/components/run/run-technical-details"
import type { RunPhaseView } from "@/lib/run-steps"
import { liveStatusNotice, type RunTechnicalSummaryDto } from "@/lib/runs"

describe("AnalysisProgressBanner — echte Phasen", () => {
  const phases: RunPhaseView[] = [
    {
      key: "prepare_documents",
      label: "Unterlagen vorbereiten",
      state: "done",
      info: "2 Quellen",
      durationSeconds: 4,
    },
    {
      key: "web_research",
      label: "Recherche vorbereiten und ausführen",
      state: "skipped",
      info: "Webrecherche nicht aktiviert",
    },
    {
      key: "draft_fields",
      label: "Feldvorschläge erstellen",
      state: "running",
    },
    {
      key: "quality_review",
      label: "Qualität und Konsistenz prüfen",
      state: "failed",
      error:
        "Die KI-Qualitätsprüfung ist fehlgeschlagen — die Feldvorschläge bleiben erhalten.",
    },
  ]

  it("zeigt Status, Zähler, Skip-Grund und Fehlermeldung je Phase", () => {
    render(<AnalysisProgressBanner steps={[]} phases={phases} />)
    // Laufende Phase erscheint in Kopfzeile UND Liste.
    expect(
      screen.getAllByText(/Feldvorschläge erstellen/).length
    ).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/2 Quellen/)).toBeInTheDocument()
    expect(screen.getByText(/\(4 s\)/)).toBeInTheDocument()
    expect(
      screen.getByText("Webrecherche nicht aktiviert", { exact: false })
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Die KI-Qualitätsprüfung ist fehlgeschlagen/)
    ).toBeInTheDocument()
    // Kein erfundener Prozentwert.
    expect(screen.queryByText(/%/)).toBeNull()
  })

  it("nennt die laufende Phase in der Kopfzeile", () => {
    render(<AnalysisProgressBanner steps={[]} phases={phases} />)
    expect(
      screen.getByText(/— Feldvorschläge erstellen…/)
    ).toBeInTheDocument()
  })
})

describe("RunTechnicalDetails", () => {
  const technical: RunTechnicalSummaryDto = {
    run_id: "run-tech-1",
    agents: [
      {
        agent_id: "A2",
        invocations: 6,
        providers: ["fake"],
        models: ["anthropic_sonnet_46"],
        input_tokens: 100,
        output_tokens: 200,
        priced_cost_chf: 0,
        has_unpriced_usage: false,
        latency_ms_total: 1234,
      },
      {
        agent_id: "A3",
        invocations: 1,
        providers: ["fake"],
        models: ["openai_gpt_54"],
        input_tokens: 50,
        output_tokens: 60,
        priced_cost_chf: 0,
        has_unpriced_usage: false,
        latency_ms_total: 456,
      },
    ],
    priced_cost_chf_total: 0,
    has_unpriced_usage: false,
    same_provider_a2_a3: true,
  }

  it("zeigt Provider/Modell/Tokens/Latenz/Run-ID nur eingeklappt", () => {
    render(<RunTechnicalDetails technical={technical} />)
    // Eingeklappt: die technischen Werte sind noch nicht sichtbar.
    expect(screen.queryByText(/run-tech-1/)).toBeNull()
    screen.getByRole("button", { name: "Technische Details" }).click()
  })

  it("kennzeichnet denselben Dienst für A2/A3 als keine Zweitmeinung", async () => {
    const { findByText, getByRole } = render(
      <RunTechnicalDetails technical={technical} />
    )
    getByRole("button", { name: "Technische Details" }).click()
    expect(
      await findByText(/keine unabhängige\s+Zweitmeinung/)
    ).toBeInTheDocument()
    expect(await findByText("run-tech-1")).toBeInTheDocument()
  })
})

describe("CompletedAnalysisBanner", () => {
  it("meldet «teilweise abgeschlossen», wenn eine Phase fehlgeschlagen ist", () => {
    render(
      <CompletedAnalysisBanner
        partialPhaseLabel="Qualität und Konsistenz prüfen"
        onGoToRequirements={vi.fn()}
      />
    )
    expect(
      screen.getByText(/Analyse teilweise abgeschlossen/)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Feldvorschläge bleiben erhalten/)
    ).toBeInTheDocument()
  })

  it("zeigt den ehrlichen Live-Hinweis (partial_live) mit Teilweise-Ikone", () => {
    render(
      <CompletedAnalysisBanner
        liveNotice={liveStatusNotice("partial_live")}
        onGoToRequirements={vi.fn()}
      />
    )
    expect(
      screen.getByText(/nicht alle Live-Schritte wurden mit echten Providern/)
    ).toBeInTheDocument()
    // Kein Hinweis bei vollständigem Live-Lauf oder Fake-Lauf.
    expect(liveStatusNotice("completed_live")).toBeNull()
    expect(liveStatusNotice(null)).toBeNull()
    expect(liveStatusNotice(undefined)).toBeNull()
  })

  it("shows neutral copy without dummy counts", () => {
    const { container } = render(
      <CompletedAnalysisBanner
        onGoToRequirements={vi.fn()}
        onShowEvidence={vi.fn()}
      />
    )
    expect(
      screen.getByText(
        "Analyse abgeschlossen. Öffnen Sie Anforderungen und Evidenz für die Ergebnisse."
      )
    ).toBeInTheDocument()
    expect(screen.queryByText(/Dummy/)).not.toBeInTheDocument()
    expect(screen.queryByText(/12 Belege/)).not.toBeInTheDocument()
    expect(screen.queryByText(/19 Anforderungen/)).not.toBeInTheDocument()
    // Stricter guard: the banner must not contain any digits at all.
    expect(container.textContent).not.toMatch(/\d/)
    expect(
      screen.getByRole("button", { name: "Zu den Anforderungen" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Belege ansehen" })
    ).toBeInTheDocument()
  })
})
