import { describe, expect, it } from "vitest"
import {
  failedPhaseLabel,
  phasesToView,
  RUN_PHASE_LABELS,
} from "@/lib/run-steps"
import type { RunPhaseDto } from "@/lib/runs"

function phase(overrides: Partial<RunPhaseDto> = {}): RunPhaseDto {
  return {
    phase_key: "prepare_documents",
    status: "succeeded",
    started_at: "2026-07-12T10:00:00Z",
    ended_at: "2026-07-12T10:00:12Z",
    error_code: null,
    detail: {},
    ...overrides,
  }
}

describe("phasesToView — echte Backend-Phasen, kein erfundener Fortschritt", () => {
  it("mapped Status, Label und Dauer 1:1", () => {
    const view = phasesToView([
      phase({ detail: { sources_frozen: 3 } }),
      phase({ phase_key: "detect_facts", status: "running", ended_at: null }),
      phase({ phase_key: "formal_checks", status: "pending", started_at: null, ended_at: null }),
    ])
    expect(view[0]).toMatchObject({
      key: "prepare_documents",
      label: "Unterlagen vorbereiten",
      state: "done",
      info: "3 Quellen",
      durationSeconds: 12,
    })
    expect(view[1].state).toBe("running")
    expect(view[1].durationSeconds).toBeUndefined()
    expect(view[2].state).toBe("pending")
  })

  it("zeigt Skip-Gründe in Klartext — nie Roh-Codes", () => {
    const view = phasesToView([
      phase({
        phase_key: "web_research",
        status: "skipped",
        detail: { reason: "web_research_not_requested" },
      }),
      phase({
        phase_key: "web_research",
        status: "skipped",
        detail: { reason: "web_research_class_blocked" },
      }),
    ])
    expect(view[0].info).toBe("Webrecherche nicht aktiviert")
    expect(view[1].info).toBe("Für diese Vertraulichkeitsstufe deaktiviert")
    expect(JSON.stringify(view)).not.toContain("web_research_not_requested")
  })

  it("zählt Vorschläge und meldet ein erreichtes Limit ehrlich", () => {
    const view = phasesToView([
      phase({
        phase_key: "draft_fields",
        detail: {
          template_drafts: 8,
          suggestions_created: 2,
          budget_stop: "llm_budget_exhausted",
        },
      }),
      phase({
        phase_key: "draft_fields",
        detail: { suggestions_created: 0, a2_status: "skipped" },
      }),
    ])
    expect(view[0].info).toBe(
      "2 Vorschläge erstellt — Limit erreicht, weitere Felder übersprungen"
    )
    expect(view[1].info).toBe("ohne KI-Vorschläge")
  })

  it("liefert deutsche Fehlermeldungen je Phase", () => {
    const view = phasesToView([
      phase({
        phase_key: "quality_review",
        status: "failed",
        error_code: "provider_error",
        detail: { a3_status: "failed" },
      }),
      phase({
        phase_key: "web_research",
        status: "failed",
        error_code: "web_research_failed",
      }),
    ])
    expect(view[0].error).toBe(
      "Die KI-Qualitätsprüfung ist fehlgeschlagen — die Feldvorschläge bleiben erhalten."
    )
    // Anforderung 13: der Fehler nennt den manuellen Ausweg (keine Sackgasse).
    expect(view[1].error).toBe(
      "Die Webrecherche ist fehlgeschlagen. Sie können Quellen manuell hinzufügen (URL oder Datei)."
    )
  })

  it("nennt Intake-only-Läufe beim Namen statt «0 Quellen»", () => {
    const view = phasesToView([
      phase({ detail: { sources_frozen: 0, intake_description: true } }),
    ])
    expect(view[0].info).toBe("Projektbeschreibung aus dem Intake")
  })
})

describe("failedPhaseLabel", () => {
  it("liefert das deutsche Label der fehlgeschlagenen Phase", () => {
    expect(
      failedPhaseLabel([
        phase(),
        phase({ phase_key: "quality_review", status: "failed" }),
      ])
    ).toBe(RUN_PHASE_LABELS.quality_review)
  })

  it("liefert null, wenn keine Phase fehlgeschlagen ist", () => {
    expect(failedPhaseLabel([phase()])).toBeNull()
  })
})
