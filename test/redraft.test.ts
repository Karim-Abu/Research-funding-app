import { describe, it, expect } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { createRedraft, RedraftError } from "@/lib/redraft"

const FIELD = "SOL.INNOVATION_SOLUTION.EDITOR"
const REDRAFT_URL = `/api/runs/r1/fields/${FIELD}/redrafts`

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
  }
}

describe("createRedraft", () => {
  it("posts, polls the operation and resolves the suggestion", async () => {
    server.use(
      http.post(REDRAFT_URL, () =>
        HttpResponse.json(
          { operation_id: "op1", resource_type: "redraft", resource_id: "d1",
            status: "queued", poll_url: "/api/v1/operations/op1" },
          { status: 202 }
        )
      ),
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
    })
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
})
