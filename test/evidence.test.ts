import { describe, it, expect } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import {
  listEvidence,
  VERIFICATION_LABELS,
  EVIDENCE_VERIFIED_HINT,
} from "@/lib/evidence"
import { MOCK_CAPABILITIES } from "@/lib/capabilities"

function anchorDoc(overrides: Record<string, unknown> = {}) {
  return {
    anchor_id: "an1",
    source_version_id: "sv1",
    fragment_id: "f1",
    quote: "Müller prüft die Förderfähigkeit.",
    verification_status: "exact_verified",
    source_id: "s1",
    source_name: "Quelle.txt",
    source_type: "txt",
    normalizer_version: "normalizer-1",
    page: null,
    section: null,
    match_type: "exact_normalized",
    human_checked_by: null,
    human_checked_at: null,
    start_offset: 0,
    end_offset: 30,
    match_score: null,
    coverage: null,
    source_accessed_at: null,
    ...overrides,
  }
}

describe("evidence client", () => {
  it("parses run-scoped anchors", async () => {
    server.use(
      http.get("/api/runs/r1/evidence", () =>
        HttpResponse.json([anchorDoc(), anchorDoc({ anchor_id: "an2", verification_status: "unverified" })])
      )
    )
    const anchors = await listEvidence("r1")
    expect(anchors).toHaveLength(2)
    expect(anchors[0].verification_status).toBe("exact_verified")
    expect(anchors[0].match_score).toBeNull()
  })

  it("maps 404 to a user-safe error", async () => {
    server.use(
      http.get("/api/runs/missing/evidence", () =>
        HttpResponse.json({ code: "not_found" }, { status: 404 })
      )
    )
    await expect(listEvidence("missing")).rejects.toThrow("nicht gefunden")
  })

  it("exposes German verification labels + the verified explanation", () => {
    expect(VERIFICATION_LABELS.exact_verified).toBe("Fundstelle bestätigt")
    expect(VERIFICATION_LABELS.unverified).toBe("Prüfen")
    expect(VERIFICATION_LABELS.rejected).toBe("Nicht bestätigt")
    expect(EVIDENCE_VERIFIED_HINT).toContain("keine inhaltliche Freigabe")
  })

  it("advertises the evidence capability while review/export stay off", () => {
    expect(MOCK_CAPABILITIES.features.evidence).toBe(true)
    expect(MOCK_CAPABILITIES.features.review).toBe(false)
    expect(MOCK_CAPABILITIES.features.export).toBe(false)
  })
})
