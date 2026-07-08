import { describe, it, expect } from "vitest"
import {
  dataClassificationFromFlat,
  flatFromDataClassification,
} from "@/lib/data-classification"
import { flatToPrivacyClass, isExternalBlocked } from "@/lib/data-class"
import {
  isCloudAllowed,
  isWebAllowed,
  mostRestrictiveDataClass,
  type DataClass,
} from "@/lib/types"

const ALL_FLAT: DataClass[] = ["public", "internal", "confidential", "nda"]

// Freezes the UI→contract DataClassification mapping so it cannot drift silently.
// R4.1: authoritative source is docs/repair/data-class-mapping.md §2 (owner-approved).
describe("dataClassificationFromFlat", () => {
  it("maps each visible DataClass to the exact contract object", () => {
    expect(dataClassificationFromFlat("public")).toEqual({
      sensitivity: "public",
      origin: "synthetic",
      processing_mode: "cloud_assisted",
      web_research_mode: "validated_public",
      nda_applies: false,
    })
    expect(dataClassificationFromFlat("internal")).toEqual({
      sensitivity: "internal",
      origin: "real_project",
      processing_mode: "deterministic_only",
      web_research_mode: "off",
      nda_applies: false,
    })
    expect(dataClassificationFromFlat("confidential")).toEqual({
      sensitivity: "confidential",
      origin: "real_project",
      processing_mode: "local_only",
      web_research_mode: "off",
      nda_applies: false,
    })
    // R4.1: NDA / gesperrt (D3) — deterministic_only, kein KI-Pfad, kein Web.
    expect(dataClassificationFromFlat("nda")).toEqual({
      sensitivity: "confidential",
      origin: "real_project",
      processing_mode: "deterministic_only",
      web_research_mode: "off",
      nda_applies: true,
    })
  })

  it("web_research_mode never loosens the class property (restrict-only)", () => {
    // Only D0/public may carry validated_public; every other class stays off.
    for (const flat of ALL_FLAT) {
      const mode = dataClassificationFromFlat(flat).web_research_mode
      if (flat === "public") {
        expect(mode).toBe("validated_public")
      } else {
        expect(mode).toBe("off")
      }
    }
  })
})

describe("flatFromDataClassification (inverse)", () => {
  it("round-trips every flat value without loss", () => {
    for (const flat of ALL_FLAT) {
      expect(flatFromDataClassification(dataClassificationFromFlat(flat))).toBe(
        flat
      )
    }
  })

  it("nda_applies wins over sensitivity — no silent marker loss", () => {
    expect(
      flatFromDataClassification({
        sensitivity: "public",
        origin: "synthetic",
        processing_mode: "cloud_assisted",
        web_research_mode: "validated_public",
        nda_applies: true,
      })
    ).toBe("nda")
  })
})

describe("flatToPrivacyClass (fail-closed)", () => {
  it("maps the four flat values onto D0–D3", () => {
    expect(flatToPrivacyClass("public")).toBe("D0_PUBLIC")
    expect(flatToPrivacyClass("internal")).toBe("D1_INTERNAL")
    expect(flatToPrivacyClass("confidential")).toBe("D2_CONFIDENTIAL_IDEA")
    expect(flatToPrivacyClass("nda")).toBe("D3_NDA_BLOCKED")
  })

  it("anything unrecognized is UNKNOWN, never D0", () => {
    expect(flatToPrivacyClass("" as DataClass)).toBe("UNKNOWN")
    expect(flatToPrivacyClass("top-secret" as DataClass)).toBe("UNKNOWN")
  })

  it("D3 and UNKNOWN are blocked from every external research surface", () => {
    expect(isExternalBlocked("D3_NDA_BLOCKED")).toBe(true)
    expect(isExternalBlocked("UNKNOWN")).toBe(true)
    expect(isExternalBlocked("D0_PUBLIC")).toBe(false)
    expect(isExternalBlocked("D1_INTERNAL")).toBe(false)
    expect(isExternalBlocked("D2_CONFIDENTIAL_IDEA")).toBe(false)
  })
})

describe("UI gates for the new nda class", () => {
  it("nda never enables cloud or web in the UI", () => {
    expect(isCloudAllowed("nda")).toBe(false)
    expect(isWebAllowed("nda")).toBe(false)
  })

  it("nda is the most restrictive flat class", () => {
    expect(mostRestrictiveDataClass(["public", "nda"])).toBe("nda")
    expect(mostRestrictiveDataClass(["confidential", "nda", "internal"])).toBe(
      "nda"
    )
    expect(mostRestrictiveDataClass(["internal", "confidential"])).toBe(
      "confidential"
    )
  })
})
