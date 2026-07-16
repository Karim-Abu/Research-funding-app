import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { AnalyseEinstellungenDialog } from "@/components/run/analyse-einstellungen-dialog"
import type { AnalyseSettings, DataClass, Role } from "@/lib/types"
import type { Origin } from "@/lib/data-classification"

function renderDialog(
  dataClass: DataClass,
  onStart = vi.fn(),
  role: Role = "member",
  options: {
    generationMode?: "unavailable" | "fake_demo" | "real_eval"
    projectOrigin?: Origin
    webAvailable?: boolean
    unavailableReason?: string
  } = {}
) {
  const generationMode = options.generationMode ?? "real_eval"
  render(
    <AnalyseEinstellungenDialog
      open
      onOpenChange={() => {}}
      role={role}
      dataClass={dataClass}
      projectOrigin={options.projectOrigin ?? "synthetic"}
      serviceAvailability={{
        ki: generationMode !== "unavailable",
        web: options.webAvailable ?? true,
        generationMode,
        unavailableReason: options.unavailableReason,
      }}
      onStart={onStart}
    />
  )
  return onStart
}

describe("AnalyseEinstellungenDialog — Side-Sheet-Layout", () => {
  it("renders as a wide side sheet with sticky footer and scrollable body", () => {
    renderDialog("public")
    const content = document.querySelector('[data-slot="sheet-content"]')
    expect(content).not.toBeNull()
    // Breite Konfigurationsansicht: ≥880px, 85vw, Cap 1000px.
    expect(content!.className).toContain("sm:min-w-[880px]")
    expect(content!.className).toContain("sm:w-[85vw]")
    expect(content!.className).toContain("sm:max-w-[1000px]")
    // Start-Button lebt im (sticky) Footer, der Body scrollt intern.
    const footer = document.querySelector('[data-slot="sheet-footer"]')
    expect(footer).not.toBeNull()
    expect(
      within(footer as HTMLElement).getByRole("button", { name: "Analyse starten" })
    ).toBeInTheDocument()
    expect(content!.querySelector(".overflow-y-auto")).not.toBeNull()
  })

  it("explains why the start button is disabled", () => {
    renderDialog("public")
    expect(screen.getByRole("button", { name: "Analyse starten" })).toBeDisabled()
    expect(
      screen.getByText("Bitte bestätigen Sie die Verarbeitung für diesen Durchlauf.")
    ).toBeInTheDocument()
  })
})

describe("AnalyseEinstellungenDialog — Deaktivierungs-Gründe (A4)", () => {
  it("internal real project: KI-Schalter erklärt die Datenklassen-Sperre", () => {
    renderDialog("internal", vi.fn(), "member", { projectOrigin: "real_project" })
    expect(
      screen.getByText(
        "Für die Vertraulichkeitsstufe «Intern» ist kein KI-Provider freigegeben — es laufen nur regelbasierte Prüfungen."
      )
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        "Nur bei Vertraulichkeitsstufe «Öffentlich» verfügbar — aktuelle Stufe: Intern."
      )
    ).toBeInTheDocument()
  })

  it("public real project: KI-Schalter nennt die Evaluationsfall-Bedingung", () => {
    renderDialog("public", vi.fn(), "member", { projectOrigin: "real_project" })
    expect(
      screen.getByText(
        "Nur für synthetische oder anonymisierte Evaluationsfälle verfügbar — dieses Projekt enthält echte Projektdaten."
      )
    ).toBeInTheDocument()
  })

  it("kein Provider: der Backend-Grund wird in Klartext angezeigt", () => {
    renderDialog("public", vi.fn(), "member", {
      generationMode: "unavailable",
      unavailableReason: "mode_deterministic_only",
    })
    expect(
      screen.getByText(
        "Dieses Projekt ist aktuell auf regelbasierte Verarbeitung beschränkt."
      )
    ).toBeInTheDocument()
  })

  it("Websuche serverseitig aus: konkreter Grund statt Generik", () => {
    renderDialog("public", vi.fn(), "member", { webAvailable: false })
    expect(
      screen.getByText("Die öffentliche Websuche ist serverseitig deaktiviert.")
    ).toBeInTheDocument()
    expect(screen.queryByText("Dienst aktuell nicht verfügbar")).toBeNull()
  })
})

describe("AnalyseEinstellungenDialog — erwartete Phasen (A2)", () => {
  it("zeigt die 6 Phasen mit ehrlichem Skip-Hinweis ohne Webrecherche", () => {
    renderDialog("public")
    const list = screen.getByTestId("expected-phases")
    expect(within(list).getByText("Unterlagen vorbereiten")).toBeInTheDocument()
    expect(
      within(list).getByText("Qualität und Konsistenz prüfen")
    ).toBeInTheDocument()
    expect(
      within(list).getByText("— Wird übersprungen — Webrecherche nicht aktiviert")
    ).toBeInTheDocument()
    // Keine erfundene Dauer-/Kostenschätzung.
    expect(within(list).queryByText(/Minuten|Sekunden|CHF/)).toBeNull()
  })

  it("kündigt Feldvorschläge ohne KI an, wenn der KI-Schalter aus ist", () => {
    renderDialog("public")
    fireEvent.click(screen.getByRole("switch", { name: /KI-Unterstützung/ }))
    const list = screen.getByTestId("expected-phases")
    expect(within(list).getByText("— ohne KI-Vorschläge")).toBeInTheDocument()
    expect(within(list).getByText("— ohne KI-Prüfung")).toBeInTheDocument()
  })
})

describe("AnalyseEinstellungenDialog — cloud-processing gate", () => {
  it("public: requires the cloud confirmation before starting a cloud run", () => {
    const onStart = renderDialog("public")
    // The cloud opt-in is on by default for public; the confirmation is required.
    expect(
      screen.getByText("Evaluationsfall – keine echten vertraulichen Daten")
    ).toBeInTheDocument()
    const start = screen.getByRole("button", { name: "Analyse starten" })
    expect(start).toBeDisabled()

    fireEvent.click(
      screen.getByLabelText("Reale KI für diesen Evaluationsdurchlauf erlauben")
    )
    expect(start).toBeEnabled()
    fireEvent.click(start)
    const settings = onStart.mock.calls[0][0] as AnalyseSettings
    expect(settings.ki).toBe(true)
    expect(settings.cloudConfirmed).toBe(true)
    expect(settings.web).toBe(false)
  })

  it("does not imply data stays local or that the provider never processes it", () => {
    renderDialog("public")
    const dialog = screen.getByText(
      /Ausgewählte Inhalte können an den konfigurierten KI-Dienst übermittelt werden/
    )
    expect(dialog).toBeInTheDocument()
    expect(screen.queryByText(/bleibt lokal/i)).toBeNull()
    expect(screen.queryByText(/niemals verarbeitet/i)).toBeNull()
    expect(screen.queryByText(/Förderchancen/i)).toBeNull()
    // No provider/model identifiers surface.
    expect(screen.queryByText(/anthropic/i)).toBeNull()
    expect(screen.queryByText(/openai|gpt|claude/i)).toBeNull()
  })

  it("confidential real project: no approved provider, run stays rule-based", () => {
    const onStart = renderDialog("confidential", vi.fn(), "member", {
      projectOrigin: "real_project",
    })
    expect(
      screen.queryByLabelText("Reale KI für diesen Evaluationsdurchlauf erlauben")
    ).toBeNull()
    expect(screen.queryByTestId("local-ai-warning")).toBeNull()
    expect(screen.getByText(
      "Für diese Datenklasse ist aktuell kein freigegebener KI-Provider konfiguriert. Die App führt nur regelbasierte Prüfungen aus."
    )).toBeInTheDocument()
    const start = screen.getByRole("button", { name: "Analyse starten" })
    expect(start).toBeEnabled() // ein regelbasierter Lauf braucht keine Freigabe
    fireEvent.click(start)
    const settings = onStart.mock.calls[0][0] as AnalyseSettings
    expect(settings.ki).toBe(false)
    expect(settings.cloudConfirmed).toBe(false)
  })

  for (const dc of ["internal", "confidential"] as const) {
    it(`${dc} real project: switch is disabled and no local opt-in is offered`, () => {
      const onStart = renderDialog(dc, vi.fn(), "member", {
        projectOrigin: "real_project",
      })
      expect(screen.getByRole("switch", { name: /KI-Unterstützung/ })).toHaveAttribute(
        "aria-disabled",
        "true"
      )
      expect(screen.queryByTestId("local-ai-warning")).toBeNull()
      expect(screen.queryByText(/lokalen Verarbeitungspfad/)).toBeNull()
      const start = screen.getByRole("button", { name: "Analyse starten" })
      expect(start).toBeEnabled()
      fireEvent.click(start)
      const settings = onStart.mock.calls[0][0] as AnalyseSettings
      expect(settings.ki).toBe(false)
      expect(settings.cloudConfirmed).toBe(false)
    })
  }

  it("fake provider is presented only as demo output", () => {
    renderDialog("public", vi.fn(), "member", { generationMode: "fake_demo" })
    expect(screen.getByText("Demo-Vorschläge")).toBeInTheDocument()
    expect(screen.getByText("Demo-Vorschlag (kein echtes KI-Modell)")).toBeInTheDocument()
    expect(screen.queryByText(/^KI-Vorschlag$/)).toBeNull()
    expect(screen.getByLabelText("Demo-Generator für diesen Durchlauf aktivieren")).toBeInTheDocument()
  })

  it("public: der Web-Toggle aktiviert die öffentliche Webrecherche", () => {
    const onStart = renderDialog("public")
    expect(
      screen.getByText("Öffentliche Webrecherche")
    ).toBeInTheDocument()
    fireEvent.click(
      screen.getByRole("switch", { name: /Öffentliche Webrecherche/ })
    )
    fireEvent.click(
      screen.getByLabelText("Reale KI für diesen Evaluationsdurchlauf erlauben")
    )
    fireEvent.click(screen.getByRole("button", { name: "Analyse starten" }))
    const settings = onStart.mock.calls[0][0] as AnalyseSettings
    expect(settings.web).toBe(true)
    expect(settings.maxWebCalls).toBe(5)
  })

  it("zeigt den Standardmodus einfach und ehrlich — ohne Dummy/Preisrätsel", () => {
    renderDialog("public")
    expect(
      screen.getByText("Projektunterlagen analysieren")
    ).toBeInTheDocument()
    // Kein erfundener Schätzwert, kein raw model key, kein Dummy-Text.
    expect(screen.queryByText(/dummy/i)).toBeNull()
    expect(screen.queryByText(/preis unbekannt/i)).toBeNull()
    expect(screen.queryByText(/anthropic|openai|gpt|claude/i)).toBeNull()
    // Erweiterte Einstellungen sind für member nicht sichtbar.
    expect(screen.queryByText("Erweiterte Einstellungen")).toBeNull()
  })

  it("lead_admin: erweiterte Einstellungen senden echte Limits", () => {
    const onStart = renderDialog("public", vi.fn(), "lead_admin")
    fireEvent.click(screen.getByText("Erweiterte Einstellungen"))
    fireEvent.change(screen.getByLabelText("Max. KI-Aufrufe pro Durchlauf"), {
      target: { value: "7" },
    })
    fireEvent.click(
      screen.getByLabelText("Reale KI für diesen Evaluationsdurchlauf erlauben")
    )
    fireEvent.click(screen.getByRole("button", { name: "Analyse starten" }))
    const settings = onStart.mock.calls[0][0] as AnalyseSettings
    expect(settings.maxLlmCalls).toBe(7)
    // Modellwahl bleibt Systementscheidung — nur als Text, nie als Auswahl.
    expect(
      screen.getByText("Modellwahl: automatisch durch das System")
    ).toBeInTheDocument()
  })

  // --- R8 Query-Freigabe im Dialog -----------------------------------------

  const PLAN_QUERIES = [
    { query_text: "robotics market size Switzerland", purpose: "market_size",
      public_safe: true, approval_required: true, approval_id: "appr-1" },
    { query_text: "robotics competitors alternatives", purpose: "competitors_alternatives",
      public_safe: true, approval_required: true, approval_id: "appr-2" },
  ]

  function planHandlers(onPlan?: () => void) {
    return [
      http.post("/api/projects/p1/market-research/plan", () => {
        onPlan?.()
        return HttpResponse.json({
          topic: { application_domain: "Robotik", technology_area: "KI",
                   target_customers: "KMU", region: "Schweiz" },
          queries: PLAN_QUERIES,
          provider_mode: "fake",
        })
      }),
      http.post("/api/search-query-approvals/:id/approve", ({ params }) =>
        HttpResponse.json({ approval_id: params.id, status: "approved" })
      ),
      http.post("/api/search-query-approvals/:id/reject", ({ params }) =>
        HttpResponse.json({ approval_id: params.id, status: "rejected" })
      ),
    ]
  }

  function renderWithProject(onStart = vi.fn()) {
    render(
      <AnalyseEinstellungenDialog
        open
        onOpenChange={() => {}}
        role="member"
        dataClass="public"
        projectId="p1"
        onStart={onStart}
      />
    )
    return onStart
  }

  it("R8: Web-Toggle lädt Suchanfragen mit Zweck-Label und Freigabe pro Query", async () => {
    server.use(...planHandlers())
    renderWithProject()
    fireEvent.click(screen.getByRole("switch", { name: /Öffentliche Webrecherche/ }))
    const list = await screen.findByTestId("query-approval-list")
    const rows = within(list).getAllByTestId("query-approval-row")
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent("Marktgrösse und Wachstum")
    expect(rows[0]).toHaveTextContent("robotics market size Switzerland")
    expect(screen.getByTestId("query-approval-count")).toHaveTextContent(
      "0 von 2 Suchanfragen freigegeben"
    )
    expect(
      screen.getByText(/Die Webrecherche wird übersprungen, bis mindestens eine/)
    ).toBeInTheDocument()

    fireEvent.click(within(rows[0]).getByRole("button", { name: /Freigeben/ }))
    await waitFor(() =>
      expect(screen.getByTestId("query-approval-count")).toHaveTextContent(
        "1 von 2 Suchanfragen freigegeben"
      )
    )
    expect(within(rows[0]).getByText("Freigegeben")).toBeInTheDocument()
    // Der Start bleibt unabhängig von der Zahl der Freigaben möglich.
    fireEvent.click(screen.getByLabelText("Reale KI für diesen Evaluationsdurchlauf erlauben"))
    expect(screen.getByRole("button", { name: "Analyse starten" })).toBeEnabled()
  })

  it("R8: Bearbeiten prüft neu (Firewall) und lehnt die alte Freigabe ab", async () => {
    let rejected: string | null = null
    server.use(
      // Der zählende Reject-Handler muss VOR dem generischen aus planHandlers()
      // stehen (MSW: zuerst registrierte Runtime-Handler haben Vorrang).
      http.post("/api/search-query-approvals/:id/reject", ({ params }) => {
        rejected = String(params.id)
        return HttpResponse.json({ approval_id: params.id, status: "rejected" })
      }),
      http.post("/api/projects/p1/market-research/queries/preview", () =>
        HttpResponse.json({
          query_text: "anomaly detection market growth",
          purpose: "market_size",
          public_safe: true,
          approval_required: true,
          approval_id: "appr-neu",
        })
      ),
      ...planHandlers()
    )
    renderWithProject()
    fireEvent.click(screen.getByRole("switch", { name: /Öffentliche Webrecherche/ }))
    const list = await screen.findByTestId("query-approval-list")
    const row = within(list).getAllByTestId("query-approval-row")[0]
    fireEvent.click(within(row).getByRole("button", { name: /Bearbeiten/ }))
    fireEvent.change(screen.getByTestId("query-edit-input"), {
      target: { value: "anomaly detection market growth QuantumFoam" },
    })
    fireEvent.click(
      within(row).getByRole("button", { name: /Prüfen und übernehmen/ })
    )
    // Der angezeigte Text ist der BEREINIGTE Text der neuen Prüfung.
    await waitFor(() =>
      expect(row).toHaveTextContent("anomaly detection market growth")
    )
    expect(rejected).toBe("appr-1")
    expect(within(row).getByText("Offen")).toBeInTheDocument()
  })

  it("R8: ohne Web-Toggle werden keine Suchanfragen geladen", async () => {
    let planned = false
    server.use(...planHandlers(() => { planned = true }))
    renderWithProject()
    await new Promise((r) => setTimeout(r, 50))
    expect(planned).toBe(false)
    expect(screen.queryByTestId("query-approval-list")).toBeNull()
  })

  // R4.1/R4.3: NDA / gesperrt (D3) — KI-Schalter bleibt deaktiviert, kein Opt-in.
  it("nda: AI stays fully blocked — no toggle, no warning panel", () => {
    const onStart = renderDialog("nda", vi.fn(), "member", {
      projectOrigin: "real_project",
    })
    expect(
      screen.getByText(/Für diese Datenklasse ist aktuell kein freigegebener KI-Provider/)
    ).toBeInTheDocument()
    // KI- UND Web-Schalter erklären konkret, warum sie deaktiviert sind (A4).
    expect(
      screen.getByText("Für gesperrte/NDA-Daten sind KI-Vorschläge deaktiviert.")
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        "Nur bei Vertraulichkeitsstufe «Öffentlich» verfügbar — aktuelle Stufe: NDA / gesperrt."
      )
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole("switch", { name: /KI-Unterstützung/ }))
    expect(screen.queryByTestId("local-ai-warning")).toBeNull()
    const start = screen.getByRole("button", { name: "Analyse starten" })
    fireEvent.click(start)
    const settings = onStart.mock.calls[0][0] as AnalyseSettings
    expect(settings.ki).toBe(false)
    expect(settings.web).toBe(false)
    expect(settings.cloudConfirmed).toBe(false)
  })
})
