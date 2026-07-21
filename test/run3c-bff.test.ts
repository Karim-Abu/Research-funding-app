// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { GET as getContextOptions } from "@/app/api/runs/[id]/fields/[field]/suggestion-context-options/route"
import { POST as acceptSuggestion } from "@/app/api/runs/[id]/fields/[field]/suggestions/[suggestion]/accept/route"


describe("RUN 3C BFF routes", () => {
  const realFetch = globalThis.fetch

  beforeEach(() => {
    process.env.FASTAPI_BRIDGE_URL = "http://backend.test/api/v1"
  })

  afterEach(() => {
    globalThis.fetch = realFetch
    delete process.env.FASTAPI_BRIDGE_URL
  })

  it("forwards the metadata-only context options route", async () => {
    let captured = ""
    globalThis.fetch = vi.fn(async (url: unknown) => {
      captured = String(url)
      return Response.json({ anchors: [], market_comparison_id: null })
    }) as unknown as typeof fetch
    const request = new Request(
      "http://localhost/api/runs/run%201/fields/FIELD%2F1/suggestion-context-options"
    )
    const response = await getContextOptions(request, {
      params: Promise.resolve({ id: "run 1", field: "FIELD/1" }),
    })
    expect(response.status).toBe(200)
    expect(captured).toBe(
      "http://backend.test/api/v1/runs/run%201/fields/FIELD%2F1/suggestion-context-options"
    )
  })

  it("forwards the required accept idempotency key and payload", async () => {
    let captured = ""
    let key = ""
    globalThis.fetch = vi.fn(async (url: unknown, init: RequestInit) => {
      captured = String(url)
      key = (init.headers as Headers).get("idempotency-key") ?? ""
      return Response.json({ suggestion_id: "s/1", draft_version_id: "v2" })
    }) as unknown as typeof fetch
    const request = new Request(
      "http://localhost/api/runs/r1/fields/f1/suggestions/s%2F1/accept",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "idempotency-key": "accept-key-123",
        },
        body: JSON.stringify({ base_version_id: "v1" }),
      }
    )
    const response = await acceptSuggestion(request, {
      params: Promise.resolve({ id: "r1", field: "f1", suggestion: "s/1" }),
    })
    expect(response.status).toBe(200)
    expect(key).toBe("accept-key-123")
    expect(captured).toBe(
      "http://backend.test/api/v1/runs/r1/fields/f1/suggestions/s%2F1/accept"
    )
  })
})
