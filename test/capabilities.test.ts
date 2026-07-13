import { afterEach, describe, expect, it } from "vitest"
import { HttpResponse, http } from "msw"
import { getCapabilities } from "@/lib/capabilities"
import { setBackendMode } from "@/lib/app-mode"
import { server } from "./server"

describe("generation capabilities", () => {
  afterEach(() => setBackendMode("mock"))

  it("fails closed when live capabilities cannot be loaded", async () => {
    setBackendMode("live")
    server.use(
      http.get("/api/capabilities", () =>
        HttpResponse.json({ code: "unavailable" }, { status: 503 })
      )
    )

    const capabilities = await getCapabilities()

    expect(capabilities.generation_mode).toBe("unavailable")
    expect(capabilities.generation_unavailable_reason).toBe(
      "capabilities_unavailable"
    )
  })

  it("keeps the explicit local mock UI labelled as demo", async () => {
    setBackendMode("mock")
    const capabilities = await getCapabilities()
    expect(capabilities.generation_mode).toBe("fake_demo")
  })
})
