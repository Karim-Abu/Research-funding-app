import { describe, it, expect, beforeEach } from "vitest"
import { getActiveProjectId, setActiveProjectId } from "@/lib/intake-store"

describe("active project id", () => {
  beforeEach(() => sessionStorage.clear())

  it("stores and reads the active project id", () => {
    expect(getActiveProjectId()).toBeNull()
    setActiveProjectId("project-123")
    expect(getActiveProjectId()).toBe("project-123")
  })
})
