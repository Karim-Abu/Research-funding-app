import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"

const push = vi.fn()
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }))

const login = vi.fn()
vi.mock("@/components/providers/app-providers", () => ({
  useSession: () => ({ login }),
}))

import LoginPage from "@/app/login/page"

describe("LoginPage", () => {
  beforeEach(() => {
    push.mockReset()
    login.mockReset()
  })

  it("logs in and navigates to the dashboard on success", async () => {
    login.mockResolvedValueOnce(undefined)
    render(<LoginPage />)
    fireEvent.change(screen.getByLabelText("E-Mail"), {
      target: { value: "anna.keller@example.test" },
    })
    fireEvent.change(screen.getByLabelText("Passwort"), {
      target: { value: "pw" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Anmelden" }))

    await waitFor(() =>
      expect(login).toHaveBeenCalledWith("anna.keller@example.test", "pw")
    )
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"))
  })

  it("shows an error and does not navigate on failure", async () => {
    login.mockRejectedValueOnce(new Error("invalid_credentials"))
    render(<LoginPage />)
    fireEvent.change(screen.getByLabelText("E-Mail"), {
      target: { value: "anna.keller@example.test" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Anmelden" }))

    await screen.findByText("E-Mail oder Passwort ist nicht korrekt.")
    expect(push).not.toHaveBeenCalled()
  })
})
