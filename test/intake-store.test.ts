import { describe, it, expect, beforeEach } from "vitest"
import {
  clearIntakeSession,
  getActiveProjectId,
  loadIntake,
  redactIntakeInSession,
  saveIntake,
  setActiveProjectId,
} from "@/lib/intake-store"
import type { DataClass, IntakeFormData } from "@/lib/types"

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

// ---------------------------------------------------------------------------
// R4.4 — Security-P0 S1: keine Rohinhalte im Browser-Storage für nicht-public
// (Owner-Tabelle docs/repair/data-class-mapping.md §6).
// ---------------------------------------------------------------------------

// Sensible Marker, die für nicht-public NIE im Browser-Storage stehen dürfen.
const IDEA = "Hochvertrauliche Projektidee Quantensensorik"
const TITLE = "Geheimes Projekt X"
const BUDGET = "547000"
const PARTNER = "Geheim Robotics AG"

function fullIntake(vertraulichkeit: DataClass | ""): IntakeFormData {
  return {
    titel: TITLE,
    projektidee: IDEA,
    innovationsfeld: "Digitalisierung & KI",
    budgetrahmen: BUDGET,
    vertraulichkeit,
    partner: [{ id: "p-1", name: PARTNER, type: "Umsetzungspartner" }],
  }
}

/** Kompletter Text-Dump von session- UND localStorage für Leak-Asserts. */
function allStorageText(): string {
  const parts: string[] = []
  for (const store of [sessionStorage, localStorage]) {
    for (let i = 0; i < store.length; i++) {
      const key = store.key(i) as string
      parts.push(key, store.getItem(key) ?? "")
    }
  }
  return parts.join("\n")
}

describe("R4.4 — kein Raw Content im Browser-Storage für nicht-public", () => {
  beforeEach(() => {
    sessionStorage.clear()
    localStorage.clear()
  })

  for (const dc of ["internal", "confidential", "nda"] as const) {
    it(`${dc}: Given Intake mit Inhalten, When gespeichert, Then kein Roh-Content im Storage`, () => {
      saveIntake(fullIntake(dc))
      const dump = allStorageText()
      expect(dump).not.toContain(IDEA)
      expect(dump).not.toContain(TITLE)
      expect(dump).not.toContain(BUDGET)
      expect(dump).not.toContain(PARTNER)
      // Die Stufe selbst ist nicht-sensitives Metadatum und bleibt lesbar.
      expect(loadIntake()?.vertraulichkeit).toBe(dc)
    })
  }

  it("unklassifiziert (leer): fail-closed — ebenfalls keine Inhalte", () => {
    saveIntake(fullIntake(""))
    const dump = allStorageText()
    expect(dump).not.toContain(IDEA)
    expect(dump).not.toContain(PARTNER)
  })

  it("public: Roundtrip bleibt unverändert (bestehende D0-UX)", () => {
    saveIntake(fullIntake("public"))
    expect(loadIntake()).toEqual(fullIntake("public"))
  })

  it("Alt-Eintrag mit Inhalt wird beim Laden eines nicht-public Intakes bereinigt", () => {
    // Given: ein VOR R4.4 gespeicherter Eintrag mit Roh-Content
    sessionStorage.setItem(INTAKE_KEY, JSON.stringify(fullIntake("confidential")))
    // When: der Store gelesen wird
    const loaded = loadIntake()
    // Then: Rückgabe UND Storage sind bereinigt, die Stufe bleibt
    expect(loaded?.projektidee).toBe("")
    expect(loaded?.vertraulichkeit).toBe("confidential")
    expect(allStorageText()).not.toContain(IDEA)
    expect(allStorageText()).not.toContain(PARTNER)
  })

  it("clearIntakeSession entfernt den Intake-Eintrag vollständig (Logout)", () => {
    saveIntake(fullIntake("public"))
    clearIntakeSession()
    expect(sessionStorage.getItem(INTAKE_KEY)).toBeNull()
    expect(loadIntake()).toBeNull()
  })

  it("redactIntakeInSession leert Inhalte, behält die Stufe (Projektwechsel)", () => {
    saveIntake(fullIntake("public"))
    redactIntakeInSession()
    const after = loadIntake()
    expect(after?.vertraulichkeit).toBe("public")
    expect(after?.projektidee).toBe("")
    expect(allStorageText()).not.toContain(IDEA)
    expect(allStorageText()).not.toContain(PARTNER)
  })
})
