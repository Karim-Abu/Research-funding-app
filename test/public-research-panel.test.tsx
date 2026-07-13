import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { PublicResearchPanel } from "@/components/quellen/public-research-panel"

const PROJECT = "p1"
const TASK = "task-1"

function acceptedHandlers() {
  return [
    http.post(`/api/projects/${PROJECT}/research-tasks`, () =>
      HttpResponse.json(
        {
          operation_id: "op-1",
          resource_type: "research_task",
          resource_id: TASK,
          status: "queued",
          poll_url: "/api/v1/operations/op-1",
        },
        { status: 202 }
      )
    ),
    http.get("/api/operations/op-1", () =>
      HttpResponse.json({
        operation_id: "op-1",
        resource_type: "research_task",
        resource_id: TASK,
        status: "succeeded",
        created_at: new Date().toISOString(),
      })
    ),
    http.get(`/api/projects/${PROJECT}/research-results`, () =>
      HttpResponse.json([
        {
          result_id: "res-1",
          task_id: TASK,
          source_url: "https://research.example.org/result/0",
          title: "Öffentliche Quelle 1",
          snippet: "Auszug",
          accessed_at: new Date().toISOString(),
          status: "candidate",
          professional_evidence: [],
          partner_role_suggestions: [],
          identity_match_status: "not_applicable",
        },
      ])
    ),
  ]
}

describe("PublicResearchPanel", () => {
  it("shows public-only warnings and no provider names", () => {
    render(<PublicResearchPanel projectId={PROJECT} />)
    expect(
      screen.getByText(/Keine vertraulichen oder personenbezogenen/)
    ).toBeInTheDocument()
    expect(screen.getByText(/Webquellen müssen fachlich geprüft/)).toBeInTheDocument()
    expect(
      screen.queryByText(/firecrawl|provider|api[_ ]?key|token/i)
    ).toBeNull()
  })

  // R4.1: D3 (NDA / gesperrt) — Webrecherche vollständig blockiert, kein Formular.
  it("nda: blocks web research entirely — no search form, no dead-end submit", () => {
    render(<PublicResearchPanel projectId={PROJECT} dataClass="nda" />)
    expect(screen.getByTestId("research-blocked")).toBeInTheDocument()
    expect(
      screen.getByText(/keine Webrecherche möglich/)
    ).toBeInTheDocument()
    expect(screen.queryByLabelText(/Öffentlicher Suchbegriff/)).toBeNull()
    expect(screen.queryByRole("button", { name: /Suchen|prüfen/ })).toBeNull()
  })

  it("runs a search and lists candidate results", async () => {
    server.use(...acceptedHandlers())
    render(<PublicResearchPanel projectId={PROJECT} />)
    fireEvent.change(screen.getByLabelText(/Öffentlicher Suchbegriff/), {
      target: { value: "Photonik Kompetenz" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }))
    await waitFor(() =>
      expect(screen.getByTestId("research-results")).toBeInTheDocument()
    )
    expect(screen.getByText("Öffentliche Quelle 1")).toBeInTheDocument()
    expect(screen.getByText("research.example.org")).toBeInTheDocument()
  })

  it("imports a selected result and marks it saved", async () => {
    let imported = false
    server.use(
      ...acceptedHandlers(),
      http.post("/api/research-results/res-1/import", () => {
        imported = true
        return HttpResponse.json(
          {
            source_id: "s1",
            project_id: PROJECT,
            name: "Öffentliche Quelle 1",
            type: "url",
            status: "processed",
            data_classification: {
              sensitivity: "public",
              origin: "public_source",
              processing_mode: "deterministic_only",
              web_research_mode: "validated_public",
              nda_applies: false,
            },
          },
          { status: 201 }
        )
      })
    )
    render(<PublicResearchPanel projectId={PROJECT} />)
    fireEvent.change(screen.getByLabelText(/Öffentlicher Suchbegriff/), {
      target: { value: "Photonik" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }))
    const importBtn = await screen.findByRole("button", {
      name: "Quelle importieren",
    })
    fireEvent.click(importBtn)
    await waitFor(() =>
      expect(screen.getByText("Als Quelle gespeichert")).toBeInTheDocument()
    )
    expect(imported).toBe(true)
  })

  it("shows a safe error when the data class is blocked (422)", async () => {
    server.use(
      http.post(`/api/projects/${PROJECT}/research-tasks`, () =>
        HttpResponse.json({ code: "web_research_blocked" }, { status: 422 })
      )
    )
    render(<PublicResearchPanel projectId={PROJECT} />)
    fireEvent.change(screen.getByLabelText(/Öffentlicher Suchbegriff/), {
      target: { value: "x" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }))
    await waitFor(() =>
      expect(
        screen.getByText(/nicht erlaubt|nicht verfügbar|Fehler/)
      ).toBeInTheDocument()
    )
  })
})
