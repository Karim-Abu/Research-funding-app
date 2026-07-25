import { describe, it, expect } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import {
  acceptFieldSuggestion,
  createRedraft,
  isA2Field,
  isDeterministicRedraftFailure,
  parseAIProposal,
  RedraftError,
  redraftFailureLabel,
  STALE_REASON_LABELS,
  staleReasonLabel,
} from "@/lib/redraft"

// 2026-07-24 — deterministische Abschnittsstruktur-Fehler tragen Klartext mit
// benanntem Marker; unbekannte Codes fallen auf null zurück (Generik greift).
describe("redraftFailureLabel", () => {
  it("nennt den fehlenden Marker im Klartext", () => {
    const label = redraftFailureLabel("section_marker_missing:4.5.2")
    expect(label).toContain("«4.5.2»")
    expect(label).toContain("wieder her")
  })

  it("kennt Mehrdeutigkeit, Reihenfolge und unbekanntes Ziel", () => {
    expect(redraftFailureLabel("section_marker_ambiguous:3.2")).toContain(
      "mehrfach"
    )
    expect(redraftFailureLabel("section_markers_out_of_order")).toContain(
      "Reihenfolge"
    )
    expect(redraftFailureLabel("section_target_unknown:9.9")).toContain(
      "nicht verfügbar"
    )
  })

  it("liefert null für unbekannte Codes", () => {
    expect(redraftFailureLabel("agent_invocation_failed")).toBeNull()
  })
})

describe("isDeterministicRedraftFailure", () => {
  it("markiert section_*-Codes als nicht wiederholbar, Providerfehler nicht", () => {
    expect(isDeterministicRedraftFailure("section_marker_missing:4.1")).toBe(true)
    expect(isDeterministicRedraftFailure("section_markers_out_of_order")).toBe(true)
    expect(isDeterministicRedraftFailure("agent_invocation_failed")).toBe(false)
    expect(isDeterministicRedraftFailure("timeout")).toBe(false)
  })
})

// RUN 4B §4 — jeder kanonische Staleness-Code hat einen Klartext; unbekannte
// Codes fallen ehrlich auf einen generischen Satz zurück (nie Roh-Enum).
describe("staleReasonLabel", () => {
  it("deckt alle neun kanonischen Codes + Legacy ab", () => {
    for (const code of [
      "draft_version_changed",
      "context_manifest_missing",
      "run_snapshot_changed",
      "primary_application_version_changed",
      "registry_version_changed",
      "field_instruction_changed",
      "anchor_changed",
      "source_version_changed",
      "market_comparison_changed",
      "stale_base_version",
    ]) {
      expect(STALE_REASON_LABELS[code]).toBeTruthy()
      expect(staleReasonLabel(code)).toBe(STALE_REASON_LABELS[code])
      expect(staleReasonLabel(code)).not.toMatch(/_/)
    }
  })

  it("unbekannter Code → generischer Klartext; leer → null", () => {
    expect(staleReasonLabel("some_future_code")).toBe(
      "Dieser Vorschlag basiert nicht mehr auf dem aktuellen Stand."
    )
    expect(staleReasonLabel(null)).toBeNull()
    expect(staleReasonLabel(undefined)).toBeNull()
  })
})

const FIELD = "SOL.INNOVATION_SOLUTION.EDITOR"
const REDRAFT_URL = `/api/runs/r1/fields/${FIELD}/redrafts`

// R5.2 — typisiertes AIProposal, wie es das Backend in operation.result liefert.
function aiProposal() {
  return {
    suggestion_text: "4.1 .. 4.2 .. 4.3 .. 4.4 .. 4.5 ..",
    used_anchor_ids: ["anchor-1"],
    missing_inputs: [{ label: "[Marktzahl fehlt]", reason: "missing_market_data" }],
    profile_id: "A2.solution_innovation",
    prompt_version: "a2_solution_innovation_v1",
    context_hash: "hash-1",
    generation_kind: "model_generated",
    model_ref: "anthropic_direct:claude-sonnet-4-6",
    created_at: "2026-07-08T00:00:00+00:00",
    data_mode: "fake_test",
    provider: "anthropic_direct",
    model: "claude-sonnet-4-6",
    usage_record_id: "usg-1",
    safety_notes: ["contains_placeholders"],
    human_review_required: true,
  }
}

function suggestionResult() {
  return {
    suggestion_id: "s1",
    operation_id: "op1",
    field_id: FIELD,
    base_version_id: "v1",
    suggested_text: "4.1 .. 4.2 .. 4.3 .. 4.4 .. 4.5 ..",
    rationale: "ok",
    evidence: [],
    open_issue_ids: [],
    placeholders: [],
    character_count: 33,
    character_limit: 25000,
    warnings: [],
    generation_kind: "model_generated",
    proposal: aiProposal(),
    ai_proposal: aiProposal(),
  }
}

describe("createRedraft", () => {
  it("posts, polls the operation and resolves the suggestion", async () => {
    let requestKey = ""
    let requestBody: Record<string, unknown> = {}
    server.use(
      http.post(REDRAFT_URL, async ({ request }) => {
        requestKey = request.headers.get("idempotency-key") ?? ""
        requestBody = await request.json() as Record<string, unknown>
        return HttpResponse.json(
          { operation_id: "op1", resource_type: "redraft", resource_id: "d1",
            status: "queued", poll_url: "/api/v1/operations/op1" },
          { status: 202 }
        )
      }),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "redraft", resource_id: "d1",
          status: "succeeded", created_at: new Date().toISOString(),
          result: suggestionResult(),
        })
      )
    )
    const suggestion = await createRedraft("r1", FIELD, "v1")
    expect(suggestion.suggestion_id).toBe("s1")
    expect(suggestion.character_limit).toBe(25000)
    // R5.2: typisiertes AIProposal kommt mit — Review bleibt zwingend.
    expect(suggestion.ai_proposal?.model_ref).toBe("anthropic_direct:claude-sonnet-4-6")
    expect(suggestion.ai_proposal?.human_review_required).toBe(true)
    expect(suggestion.ai_proposal?.missing_inputs[0]?.label).toBe("[Marktzahl fehlt]")
    expect(requestKey).toMatch(/^[a-f0-9]{32}$/)
    expect(requestBody.improvement_mode).toBe("clearer")
    expect(requestBody.selected_anchor_ids).toEqual([])
  })

  // R5.2: fail-closed — ein Proposal ohne human_review_required=true wird verworfen.
  it("drops a malformed ai_proposal instead of trusting it", async () => {
    const bad = { ...suggestionResult(), ai_proposal: { ...aiProposal(), human_review_required: false } }
    server.use(
      http.post(REDRAFT_URL, () =>
        HttpResponse.json({ operation_id: "op1" }, { status: 202 })
      ),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "redraft", resource_id: "d1",
          status: "succeeded", created_at: new Date().toISOString(),
          result: bad,
        })
      )
    )
    const suggestion = await createRedraft("r1", FIELD, "v1")
    expect(suggestion.suggestion_id).toBe("s1")
    expect(suggestion.ai_proposal).toBeUndefined()
  })

  it("parseAIProposal rejects non-objects and missing fields", () => {
    expect(parseAIProposal(null)).toBeNull()
    expect(parseAIProposal("x")).toBeNull()
    expect(parseAIProposal({})).toBeNull()
    expect(parseAIProposal(aiProposal())).not.toBeNull()
  })

  // R5.6: six A2-enabled fields now (mirrors the backend allow-list).
  it("isA2Field covers the six enabled fields and rejects others", () => {
    expect(isA2Field("SOL.INNOVATION_SOLUTION.EDITOR")).toBe(true)
    expect(isA2Field("VC.BUSINESS_TARGETS_MODEL.EDITOR")).toBe(true)
    expect(isA2Field("INTRO.APP.ABSTRACT")).toBe(true)
    expect(isA2Field("INTRO.APP.EXECUTIVE_SUMMARY")).toBe(true)
    expect(isA2Field("ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS")).toBe(true)
    expect(isA2Field("PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION")).toBe(true)
    expect(isA2Field("INTRO.APP.NAME")).toBe(false)
    expect(isA2Field(null)).toBe(false)
  })

  it("maps 503 to an ai_unavailable RedraftError", async () => {
    server.use(
      http.post(REDRAFT_URL, () =>
        HttpResponse.json({ code: "ai_unavailable" }, { status: 503 })
      )
    )
    await expect(createRedraft("r1", FIELD, "v1")).rejects.toMatchObject({
      status: 503,
      code: "ai_unavailable",
      reasonCode: null,
    })
  })

  // R4.2: reason_code + freigegebener Text kommen aus dem 503-Body.
  it("parses reason_code and shows the approved catalog text", async () => {
    server.use(
      http.post(REDRAFT_URL, () =>
        HttpResponse.json(
          {
            code: "ai_unavailable",
            reason_code: "nda_locked",
            detail: "Für gesperrte/NDA-Daten sind KI-Vorschläge deaktiviert.",
          },
          { status: 503 }
        )
      )
    )
    const err = await createRedraft("r1", FIELD, "v1").catch((e) => e)
    expect(err).toBeInstanceOf(RedraftError)
    expect(err.reasonCode).toBe("nda_locked")
    expect(err.message).toBe(
      "Für gesperrte/NDA-Daten sind KI-Vorschläge deaktiviert."
    )
  })

  it("carries reason_code from a failed async operation", async () => {
    server.use(
      http.post(REDRAFT_URL, () =>
        HttpResponse.json({ operation_id: "op1" }, { status: 202 })
      ),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "redraft", resource_id: "d1",
          status: "failed", created_at: new Date().toISOString(),
          error: {
            code: "mode_deterministic_only",
            reason_code: "mode_deterministic_only",
          },
        })
      )
    )
    const err = await createRedraft("r1", FIELD, "v1").catch((e) => e)
    expect(err).toBeInstanceOf(RedraftError)
    expect(err.reasonCode).toBe("mode_deterministic_only")
    expect(err.message).toBe(
      "Dieses Projekt ist aktuell auf regelbasierte Verarbeitung beschränkt."
    )
  })

  it("maps 409 to a stale_base_version RedraftError", async () => {
    server.use(
      http.post(REDRAFT_URL, () =>
        HttpResponse.json({ code: "stale_base_version" }, { status: 409 })
      )
    )
    const err = await createRedraft("r1", FIELD, "stale").catch((e) => e)
    expect(err).toBeInstanceOf(RedraftError)
    expect(err.status).toBe(409)
  })

  it("rejects when the operation fails", async () => {
    server.use(
      http.post(REDRAFT_URL, () =>
        HttpResponse.json({ operation_id: "op1" }, { status: 202 })
      ),
      http.get("/api/operations/op1", () =>
        HttpResponse.json({
          operation_id: "op1", resource_type: "redraft", resource_id: "d1",
          status: "failed", created_at: new Date().toISOString(),
          error: { code: "character_limit_exceeded" },
        })
      )
    )
    await expect(createRedraft("r1", FIELD, "v1")).rejects.toBeInstanceOf(RedraftError)
  })

  it("accepts a manifest suggestion with an idempotency key", async () => {
    let requestKey = ""
    server.use(
      http.post(
        `/api/runs/r1/fields/${FIELD}/suggestions/s1/accept`,
        ({ request }) => {
          requestKey = request.headers.get("idempotency-key") ?? ""
          return HttpResponse.json({
            suggestion_id: "s1",
            draft_version_id: "v2",
            status: "accepted",
            idempotent_replay: false,
          })
        }
      )
    )
    const response = await acceptFieldSuggestion("r1", FIELD, "s1", "v1")
    expect(response.draft_version_id).toBe("v2")
    expect(requestKey).toMatch(/^[a-f0-9]{32}$/)
  })
})
