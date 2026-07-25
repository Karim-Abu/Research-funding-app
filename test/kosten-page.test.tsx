import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock("@/components/kosten/kosten-screen", () => ({
  KostenScreen: () => <div data-testid="kosten-screen">live costs</div>,
}))

import KostenPage from "@/app/kosten/page"

describe("KostenPage", () => {
  it("rendert die Kostenansicht ohne eine clientseitig abgeleitete Rolle", () => {
    render(<KostenPage />)
    expect(screen.getByTestId("kosten-screen")).toHaveTextContent("live costs")
  })
})
