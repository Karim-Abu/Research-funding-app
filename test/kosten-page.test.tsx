import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const session = vi.hoisted(() => ({
  mode: "live" as "live" | "mock",
  user: null as null | { effective_role: "lead_admin" | "member" },
}))

vi.mock("@/components/providers/app-providers", () => ({
  useSession: () => session,
}))

vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock("@/components/kosten/kosten-screen", () => ({
  KostenScreen: ({ role }: { role: string }) => <div data-testid="kosten-role">{role}</div>,
}))

import KostenPage from "@/app/kosten/page"

describe("KostenPage Rollenauflösung", () => {
  beforeEach(() => {
    session.mode = "live"
    session.user = null
  })

  it("fällt während einer ungeladenen Live-Sitzung sicher auf member zurück", () => {
    render(<KostenPage />)
    expect(screen.getByTestId("kosten-role")).toHaveTextContent("member")
  })

  it("verwendet die effektive Rolle der Live-Sitzung", () => {
    session.user = { effective_role: "lead_admin" }
    render(<KostenPage />)
    expect(screen.getByTestId("kosten-role")).toHaveTextContent("lead_admin")
  })
})
