import { describe, it, expect } from "vitest"
import { dataClassificationFromFlat } from "@/lib/data-classification"

// Freezes the UI→contract DataClassification mapping so it cannot drift silently.
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
  })
})
