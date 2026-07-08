import { describe, it, expect, beforeEach } from "vitest"
import {
  getActiveProjectId,
  loadIntake,
  setActiveProjectId,
} from "@/lib/intake-store"
import type { IntakeFormData } from "@/lib/types"

const INTAKE_KEY = "rf_current_intake"

function seedIntake(vertraulichkeit: unknown): void {
  const data: Omit<IntakeFormData, "vertraulichkeit"> & {
    vertraulichkeit: unknown
  } = {
    titel: "T",
    projektidee: "Idee",
    innovationsfeld: "",
    budgetrahmen: "",
    vertraulichkeit,
    partner: [],
  }
  sessionStorage.setItem(INTAKE_KEY, JSON.stringify(data))
}

describe("active project id", () => {
  beforeEach(() => sessionStorage.clear())

  it("stores and reads the active project id", () => {
    expect(getActiveProjectId()).toBeNull()
    setActiveProjectId("project-123")
    expect(getActiveProjectId()).toBe("project-123")
  })
})

// R4.1 — Migrationszuordnung Bestandswerte (docs/repair/data-class-mapping.md §4.1).
describe("legacy confidentiality normalization", () => {
  beforeEach(() => sessionStorage.clear())

  it("keeps the four current values unchanged", () => {
    for (const v of ["public", "internal", "confidential", "nda"]) {
      seedIntake(v)
      expect(loadIntake()?.vertraulichkeit).toBe(v)
    }
  })

  it("nda is no longer downgraded to confidential (no silent marker loss)", () => {
    seedIntake("nda")
    expect(loadIntake()?.vertraulichkeit).toBe("nda")
  })

  it("maps legacy public variants to public", () => {
    for (const v of ["public_synthetic", "public_external"]) {
      seedIntake(v)
      expect(loadIntake()?.vertraulichkeit).toBe("public")
    }
  })

  it("unknown values collapse to empty (selection forced, fail-closed)", () => {
    for (const v of ["top-secret", 42, null]) {
      seedIntake(v)
      expect(loadIntake()?.vertraulichkeit).toBe("")
    }
  })
})
