import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { beforeEach, describe, expect, it } from "vitest"
import { BudgetForm } from "@/components/partner/budget-form"
import { server } from "./server"

function projectBody(overrides: Record<string, unknown> = {}) {
  const now = new Date().toISOString()
  return {
    project_id: "p-1",
    workspace_id: "ws",
    title: "T",
    description: "d",
    funding_instrument_profile_id: "f",
    data_classification: {
      sensitivity: "public",
      origin: "synthetic",
      processing_mode: "deterministic_only",
      web_research_mode: "off",
      nda_applies: false,
    },
    status: "draft",
    created_at: now,
    updated_at: now,
    active_run_id: null,
    duration_months: null,
    duration_status: "not_derivable",
    duration_reason_code: "duration_dates_missing",
    primary_application_source_id: null,
    primary_application_status: "not_configured",
    ...overrides,
  }
}

function precheckBody(overrides: Record<string, unknown> = {}) {
  return {
    figures: {
      direct_costs_chf: 100000,
      own_contribution_chf: 45000,
      cash_contribution_chf: 5000,
      requested_funding_chf: 50000,
      implementation_contribution_chf: 50000,
      implementation_share_percent: 50.0,
      cash_share_percent: 5.0,
      funding_share_percent: 50.0,
      exception_claimed: false,
      ...(overrides.figures as Record<string, unknown> | undefined),
    },
    checks: (overrides.checks as unknown[]) ?? [
      precheckCheck(),
      precheckCheck({
        rule_id: "INNO.BUDGET.CASH_MIN5",
        title: "Barbeitrag mindestens 5 %",
        condition: { type: "min_percent", min: 5 },
        reason: "Barbeitrag 5% ≥ 5%.",
      }),
    ],
  }
}

function precheckCheck(overrides: Record<string, unknown> = {}) {
  return {
    rule_id: "INNO.BUDGET.IMPLEMENTATION_SHARE_40_60",
    requirement_id: "REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60",
    title: "Beitrag der Umsetzungspartner 40–60 %",
    status: "fulfilled",
    reason: "Umsetzungsanteil 50% liegt in 40–60%.",
    observed: { percent: 50.0 },
    condition: { type: "range_percent", min: 40, max: 60 },
    severity: "blocker",
    source_ref: "official_program_page_2026",
    source_version: "2026",
    last_checked: "2026-07-01",
    rule_version: "1.1.0",
    ...overrides,
  }
}

describe("BudgetForm", () => {
  beforeEach(() => {
    server.use(
      http.get("/api/projects/p-1", () => HttpResponse.json(projectBody())),
      http.get("/api/projects/p-1/budget/precheck", () =>
        HttpResponse.json(precheckBody())
      )
    )
  })

  it("patches entered values and sends empty inputs as null, never 0", async () => {
    let patchBody: Record<string, unknown> | null = null
    server.use(
      http.patch("/api/projects/p-1", async ({ request }) => {
        patchBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(projectBody(patchBody ?? {}))
      })
    )
    render(<BudgetForm projectId="p-1" />)

    fireEvent.change(
      screen.getByLabelText("Direkte Projektkosten (ohne Overhead)"),
      { target: { value: "100000" } }
    )
    fireEvent.change(screen.getByLabelText("Eigenleistung Umsetzungspartner"), {
      target: { value: "45000" },
    })
    fireEvent.change(screen.getByLabelText("Barbeitrag (Cash)"), {
      target: { value: "5000,50" },
    })
    // total_requested_funding stays empty → must be null, not 0.
    fireEvent.change(
      screen.getByLabelText("Begründung für Ausnahme (optional)"),
      { target: { value: "   " } } // whitespace only → null
    )
    fireEvent.click(screen.getByRole("button", { name: "Budget speichern" }))

    await waitFor(() =>
      expect(screen.getByText("Budgetangaben gespeichert.")).toBeInTheDocument()
    )
    expect(patchBody).toEqual({
      direct_total_project_costs_excluding_overhead: 100000,
      implementation_own_contribution: 45000,
      cash_contribution: 5000.5,
      total_requested_funding: null,
      total_requested_funding_including_overhead: null,
      budget_exception_basis: null,
    })
  })

  it("shows derived duration read-only and never offers a duration input", async () => {
    server.use(
      http.get("/api/projects/p-1", () =>
        HttpResponse.json(
          projectBody({
            duration_months: 18,
            duration_status: "derived",
            duration_reason_code: "duration_derived",
          })
        )
      )
    )
    render(<BudgetForm projectId="p-1" />)
    expect(await screen.findByText("18 Monate")).toBeInTheDocument()
    expect(screen.getByText(/nicht separat bearbeitbar/)).toBeInTheDocument()
    expect(screen.queryByLabelText("Projektdauer (Monate)")).toBeNull()
  })

  it("zeigt die Vorprüfung mit Identität, Anteilen und «Erfüllt»", async () => {
    render(<BudgetForm projectId="p-1" />)
    const panel = await screen.findByTestId("budget-precheck")
    // Identität Own + Cash = Umsetzungspartnerbeitrag mit echten Zahlen.
    await waitFor(() =>
      expect(screen.getByTestId("precheck-contribution")).toHaveTextContent(
        /45.?000 \+ 5.?000 = 50.?000 CHF \(50 % der direkten Projektkosten\)/
      )
    )
    expect(screen.getByTestId("precheck-cash")).toHaveTextContent(/^5 %/)
    expect(screen.getByTestId("precheck-funding")).toHaveTextContent(/^50 %/)
    expect(panel).toHaveTextContent("Beitrag der Umsetzungspartner 40–60 %")
    // Beide Regeln «Erfüllt» — grünes Vorprüfungs-Vokabular.
    const badges = screen.getAllByText("Erfüllt")
    expect(badges).toHaveLength(2)
  })

  it("rendert Prüfen/Blocker/Angabe fehlt mit ehrlichen Hinweisen", async () => {
    server.use(
      http.get("/api/projects/p-1/budget/precheck", () =>
        HttpResponse.json(
          precheckBody({
            figures: { exception_claimed: true },
            checks: [
              precheckCheck({
                status: "review",
                reason: "Umsetzungsanteil 65% ausserhalb 40–60%.",
              }),
              precheckCheck({
                rule_id: "INNO.BUDGET.CASH_MIN5",
                title: "Barbeitrag mindestens 5 %",
                status: "blocker",
                reason: "Barbeitrag 3% < 5%.",
              }),
            ],
          })
        )
      )
    )
    render(<BudgetForm projectId="p-1" />)
    expect(await screen.findByText("Prüfen")).toBeInTheDocument()
    expect(screen.getByText("Blocker")).toBeInTheDocument()
    // Ausnahme geltend gemacht → menschliche Prüfung, keine Akzeptanz-Behauptung.
    expect(
      screen.getByText(/wird von Menschen geprüft — die App bestätigt keine Ausnahme/)
    ).toBeInTheDocument()
  })

  it("zeigt «Angabe fehlt» statt eines roten Falschurteils bei fehlenden Werten", async () => {
    server.use(
      http.get("/api/projects/p-1/budget/precheck", () =>
        HttpResponse.json(
          precheckBody({
            figures: {
              direct_costs_chf: null,
              own_contribution_chf: null,
              cash_contribution_chf: null,
              requested_funding_chf: null,
              implementation_contribution_chf: null,
              implementation_share_percent: null,
              cash_share_percent: null,
              funding_share_percent: null,
              exception_claimed: false,
            },
            checks: [
              precheckCheck({
                status: "missing",
                reason: "Budgetangaben für die Anteilsberechnung fehlen.",
              }),
              precheckCheck({
                rule_id: "INNO.BUDGET.CASH_MIN5",
                title: "Barbeitrag mindestens 5 %",
                status: "missing",
                reason: "Budgetangaben für den Barbeitrag fehlen.",
              }),
            ],
          })
        )
      )
    )
    render(<BudgetForm projectId="p-1" />)
    const panel = await screen.findByTestId("budget-precheck")
    await waitFor(() =>
      expect(screen.getAllByText("Angabe fehlt").length).toBeGreaterThanOrEqual(5)
    )
    expect(panel).not.toHaveTextContent("Blocker")
  })

  it("erklärt Regelquelle und Stand nur eingeklappt unter «Warum wird das geprüft?»", async () => {
    render(<BudgetForm projectId="p-1" />)
    await screen.findByTestId("budget-precheck")
    // Eingeklappt: die Quelle ist noch nicht sichtbar.
    expect(screen.queryByText(/official_program_page_2026/)).toBeNull()
    fireEvent.click(
      screen.getByRole("button", { name: "Warum wird das geprüft?" })
    )
    expect(
      await screen.findByText(/muss 40–60 % der direkten Projektkosten betragen/)
    ).toBeInTheDocument()
    expect(
      screen.getAllByText(/official_program_page_2026/).length
    ).toBeGreaterThanOrEqual(1)
    expect(
      screen.getAllByText(/Regelstand 1.1.0/).length
    ).toBeGreaterThanOrEqual(1)
  })

  it("lädt die Vorprüfung nach erfolgreichem Speichern neu", async () => {
    let precheckCalls = 0
    server.use(
      http.get("/api/projects/p-1/budget/precheck", () => {
        precheckCalls += 1
        return HttpResponse.json(precheckBody())
      }),
      http.patch("/api/projects/p-1", async ({ request }) =>
        HttpResponse.json(
          projectBody((await request.json()) as Record<string, unknown>)
        )
      )
    )
    render(<BudgetForm projectId="p-1" />)
    await screen.findByTestId("budget-precheck")
    const before = precheckCalls
    fireEvent.click(screen.getByRole("button", { name: "Budget speichern" }))
    await waitFor(() =>
      expect(screen.getByText("Budgetangaben gespeichert.")).toBeInTheDocument()
    )
    await waitFor(() => expect(precheckCalls).toBeGreaterThan(before))
  })
})
