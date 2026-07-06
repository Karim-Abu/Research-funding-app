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
    ...overrides,
  }
}

describe("BudgetForm", () => {
  beforeEach(() => {
    server.use(
      http.get("/api/projects/p-1", () => HttpResponse.json(projectBody()))
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
    fireEvent.change(screen.getByLabelText("Projektdauer (Monate)"), {
      target: { value: "24" },
    })
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
      duration_months: 24,
      budget_exception_basis: null,
    })
  })

  it("rejects a non-integer duration without sending a PATCH", async () => {
    render(<BudgetForm projectId="p-1" />)
    fireEvent.change(screen.getByLabelText("Projektdauer (Monate)"), {
      target: { value: "0" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Budget speichern" }))
    expect(
      await screen.findByText(/Projektdauer als ganze Monate/)
    ).toBeInTheDocument()
  })
})
