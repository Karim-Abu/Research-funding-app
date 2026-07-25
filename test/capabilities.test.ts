import { afterEach, describe, expect, it } from "vitest"
import { HttpResponse, http } from "msw"
import {
  capabilitiesSelfHealing,
  getCapabilities,
  MOCK_CAPABILITIES,
  type Capabilities,
} from "@/lib/capabilities"
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

describe("capabilitiesSelfHealing", () => {
  const withReadiness = (
    overrides: Partial<Capabilities>
  ): Capabilities => ({ ...MOCK_CAPABILITIES, ...overrides })

  it("is true for an expired/never-run preflight (backend auto-refreshes)", () => {
    expect(
      capabilitiesSelfHealing(
        withReadiness({
          ai_unavailable_reason: "live_preflight_expired",
          feature_readiness: {
            field_suggestions: {
              status: "configured_unverified",
              available: false,
              reason_code: "live_preflight_expired",
            },
          },
        })
      )
    ).toBe(true)

    expect(
      capabilitiesSelfHealing(
        withReadiness({
          feature_readiness: {
            web_research: {
              status: "configured_unverified",
              available: false,
              reason_code: "firecrawl_preflight_expired",
            },
          },
        })
      )
    ).toBe(true)
  })

  it("is false for genuine, non-self-healing reasons (no endless polling)", () => {
    for (const reason of ["live_fake_conflict", "nda_locked", "firecrawl_key_missing"]) {
      expect(
        capabilitiesSelfHealing(
          withReadiness({
            ai_unavailable_reason: reason,
            feature_readiness: {
              field_suggestions: {
                status: "error",
                available: false,
                reason_code: reason,
              },
            },
          })
        )
      ).toBe(false)
    }
  })

  it("is false once everything is ready", () => {
    expect(
      capabilitiesSelfHealing(
        withReadiness({
          ai_available: true,
          ai_unavailable_reason: null,
          generation_unavailable_reason: null,
          feature_readiness: {
            field_suggestions: { status: "ready", available: true, reason_code: null },
            web_research: { status: "ready", available: true, reason_code: null },
          },
        })
      )
    ).toBe(false)
  })
})
