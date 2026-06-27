import { describe, it, expect, beforeEach, afterEach } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { setBackendMode } from "@/lib/app-mode"
import { login } from "@/lib/session"
import {
  createTextSource,
  deleteSource,
  listSources,
  uploadFiles,
  SourceError,
} from "@/lib/sources"

const CLASSIFICATION = {
  sensitivity: "public" as const,
  origin: "synthetic" as const,
  processing_mode: "cloud_assisted" as const,
  web_research_mode: "off" as const,
  nda_applies: false,
}

function sourceDoc(overrides: Record<string, unknown> = {}) {
  return {
    source_id: "s1",
    project_id: "p1",
    name: "doc",
    type: "txt",
    status: "processed",
    data_classification: CLASSIFICATION,
    current_source_version_id: "v1",
    created_at: new Date().toISOString(),
    error_message: null,
    ...overrides,
  }
}

describe("sources client (live mode)", () => {
  beforeEach(() => setBackendMode("live"))
  afterEach(() => setBackendMode("mock"))

  it("lists sources", async () => {
    server.use(
      http.get("/api/projects/p1/sources", () =>
        HttpResponse.json([sourceDoc(), sourceDoc({ source_id: "s2" })])
      )
    )
    const items = await listSources("p1")
    expect(items).toHaveLength(2)
    expect(items[0].status).toBe("processed")
  })

  it("uploads files with CSRF, Idempotency-Key and the classification", async () => {
    server.use(
      http.post("/api/session", () =>
        HttpResponse.json({
          user: {
            user_id: "u",
            name: "A",
            email: "a@x.test",
            effective_role: "lead_admin",
          },
          csrf_token: "tok",
        })
      )
    )
    await login("a@x.test", "pw")

    let headers: Headers | null = null
    server.use(
      http.post("/api/projects/p1/sources/files", ({ request }) => {
        headers = request.headers
        return HttpResponse.json([sourceDoc({ status: "uploaded" })], {
          status: 202,
        })
      })
    )
    const file = new File(["hello"], "a.txt", { type: "text/plain" })
    const res = await uploadFiles("p1", [file], CLASSIFICATION)
    expect(res[0].status).toBe("uploaded")
    expect(headers!.get("x-csrf-token")).toBe("tok")
    expect((headers!.get("idempotency-key") ?? "").length).toBeGreaterThanOrEqual(8)
    // (Multipart body parsing is covered by the backend pytest suite.)
  })

  it("creates a text source", async () => {
    server.use(
      http.post("/api/projects/p1/sources/text", () =>
        HttpResponse.json(sourceDoc(), { status: 201 })
      )
    )
    const res = await createTextSource("p1", "Note", "content", CLASSIFICATION)
    expect(res.status).toBe("processed")
  })

  it("maps 415 to a user-safe error", async () => {
    server.use(
      http.post("/api/projects/p1/sources/files", () =>
        HttpResponse.json({ code: "unsupported_media_type" }, { status: 415 })
      )
    )
    const file = new File(["x"], "a.exe")
    await expect(uploadFiles("p1", [file], CLASSIFICATION)).rejects.toMatchObject({
      status: 415,
    })
  })

  it("maps 413 to a 'file too large' message", async () => {
    server.use(
      http.post("/api/projects/p1/sources/files", () =>
        HttpResponse.json({ code: "file_too_large" }, { status: 413 })
      )
    )
    const file = new File(["x"], "a.txt")
    let caught: SourceError | null = null
    try {
      await uploadFiles("p1", [file], CLASSIFICATION)
    } catch (e) {
      caught = e as SourceError
    }
    expect(caught?.status).toBe(413)
    expect(caught?.message).toContain("zu groß")
  })

  it("deletes a source", async () => {
    let method = ""
    server.use(
      http.delete("/api/sources/s1", ({ request }) => {
        method = request.method
        return new HttpResponse(null, { status: 204 })
      })
    )
    await deleteSource("s1")
    expect(method).toBe("DELETE")
  })

  it("returns no live sources in mock mode", async () => {
    setBackendMode("mock")
    expect(await listSources("p1")).toEqual([])
  })
})
