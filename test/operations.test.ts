import { describe, it, expect } from "vitest"
import { http, HttpResponse } from "msw"
import { server } from "./server"
import { pollOperation, type AsyncOperationDto } from "@/lib/operations"

function opDoc(overrides: Record<string, unknown> = {}) {
  return {
    operation_id: "op1",
    resource_type: "run",
    resource_id: "r1",
    status: "running",
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

describe("pollOperation", () => {
  it("polls until a terminal status then stops", async () => {
    let calls = 0
    server.use(
      http.get("/api/operations/op1", () => {
        calls += 1
        return HttpResponse.json(opDoc({ status: calls < 2 ? "running" : "succeeded" }))
      })
    )
    const terminal = await new Promise<AsyncOperationDto>((resolve) => {
      pollOperation("op1", { intervalMs: 5, onTerminal: resolve })
    })
    expect(terminal.status).toBe("succeeded")
    expect(calls).toBeGreaterThanOrEqual(2)
  })

  it("stop() halts polling (unmount cleanup)", async () => {
    let calls = 0
    server.use(
      http.get("/api/operations/op2", () => {
        calls += 1
        return HttpResponse.json(opDoc({ operation_id: "op2", status: "running" }))
      })
    )
    const handle = pollOperation("op2", { intervalMs: 5 })
    await new Promise((r) => setTimeout(r, 40))
    handle.stop()
    const snapshot = calls
    await new Promise((r) => setTimeout(r, 40))
    expect(calls).toBe(snapshot)
  })

  it("stops after bounded errors (never polls forever)", async () => {
    let calls = 0
    server.use(
      http.get("/api/operations/op3", () => {
        calls += 1
        return new HttpResponse(null, { status: 500 })
      })
    )
    await new Promise<void>((resolve) => {
      const handle = pollOperation("op3", { intervalMs: 3, maxErrors: 3 })
      setTimeout(() => {
        handle.stop()
        resolve()
      }, 80)
    })
    expect(calls).toBeLessThanOrEqual(6)
  })
})
