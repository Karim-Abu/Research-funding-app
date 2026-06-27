// @vitest-environment node
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest"
import { forwardToBridge } from "@/lib/bridge"

describe("forwardToBridge", () => {
  const realFetch = globalThis.fetch

  beforeEach(() => {
    process.env.FASTAPI_BRIDGE_URL = "http://backend.test/api/v1"
  })
  afterEach(() => {
    globalThis.fetch = realFetch
    delete process.env.FASTAPI_BRIDGE_URL
  })

  it("forwards allow-listed headers, body and query string to the bridge", async () => {
    let capturedUrl = ""
    let capturedHeaders: Headers | null = null
    globalThis.fetch = vi.fn(async (url: unknown, init: RequestInit) => {
      capturedUrl = String(url)
      capturedHeaders = init.headers as Headers
      return new Response(JSON.stringify({ ok: true }), {
        status: 201,
        headers: { "content-type": "application/json", "x-correlation-id": "cid-1" },
      })
    }) as unknown as typeof fetch

    const request = new Request(
      "http://localhost:3000/api/projects?cursor=abc",
      {
        method: "POST",
        headers: {
          cookie: "rf_session=s",
          origin: "http://localhost:3000",
          "content-type": "application/json",
          "x-csrf-token": "tok",
          "idempotency-key": "key12345",
        },
        body: JSON.stringify({ title: "x" }),
      }
    )

    const res = await forwardToBridge(request, "/projects")
    expect(capturedUrl).toBe("http://backend.test/api/v1/projects?cursor=abc")
    expect(capturedHeaders!.get("cookie")).toBe("rf_session=s")
    expect(capturedHeaders!.get("origin")).toBe("http://localhost:3000")
    expect(capturedHeaders!.get("x-csrf-token")).toBe("tok")
    expect(capturedHeaders!.get("idempotency-key")).toBe("key12345")
    expect(res.status).toBe(201)
    expect(res.headers.get("x-correlation-id")).toBe("cid-1")
  })

  it("propagates Set-Cookie from the bridge response", async () => {
    globalThis.fetch = vi.fn(
      async () =>
        new Response(null, {
          status: 204,
          headers: { "set-cookie": "rf_session=abc; HttpOnly; Path=/" },
        })
    ) as unknown as typeof fetch

    const request = new Request("http://localhost:3000/api/session", {
      method: "DELETE",
      headers: { origin: "http://localhost:3000", "x-csrf-token": "t" },
    })
    const res = await forwardToBridge(request, "/session")
    expect(res.status).toBe(204)
    expect(res.headers.get("set-cookie")).toContain("rf_session=abc")
  })

  it("returns 502 when the bridge URL is not configured", async () => {
    delete process.env.FASTAPI_BRIDGE_URL
    const request = new Request("http://localhost:3000/api/health", {
      method: "GET",
    })
    const res = await forwardToBridge(request, "/health")
    expect(res.status).toBe(502)
  })
})
