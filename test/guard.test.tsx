import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { server } from "./server"

const replace = vi.fn()
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/",
}))

import { AppProviders } from "@/components/providers/app-providers"

describe("AppProviders auth guard", () => {
  beforeEach(() => replace.mockReset())

  it("redirects unauthenticated users to /login in live mode", async () => {
    server.use(
      http.get("/api/session", () => new HttpResponse(null, { status: 401 }))
    )
    render(
      <AppProviders mode="live">
        <div>content</div>
      </AppProviders>
    )
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"))
  })

  it("does not redirect in mock mode", async () => {
    render(
      <AppProviders mode="mock">
        <div>content</div>
      </AppProviders>
    )
    // Allow the bootstrap effect to settle.
    await waitFor(() => expect(replace).not.toHaveBeenCalled())
  })
})
