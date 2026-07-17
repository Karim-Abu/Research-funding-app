// Modusabhängige CTA- und Herkunfts-Labels (Anf. 1/4): Live, Demo und
// Strukturvorlage sind textlich eindeutig unterscheidbar.
import { describe, expect, it } from "vitest"

import {
  GENERATION_KIND_BADGE_CLASS,
  generationActionLabel,
  generationLabel,
} from "@/lib/generation-kind"

describe("generation-kind", () => {
  it("Aktionslabel je Modus", () => {
    expect(generationActionLabel("model_generated")).toBe("Text mit KI verbessern")
    expect(generationActionLabel("fake_demo")).toBe("Demo-Vorschlag erstellen")
    expect(generationActionLabel("rule_template")).toBe("Vorschlag erstellen")
    expect(generationActionLabel(null)).toBe("Vorschlag erstellen")
    expect(generationActionLabel(undefined)).toBe("Vorschlag erstellen")
  })

  it("Herkunftslabel je Modus", () => {
    expect(generationLabel("model_generated")).toBe("Live-KI-Vorschlag")
    expect(generationLabel("fake_demo")).toBe("Demo-Vorschlag (kein echtes KI-Modell)")
    expect(generationLabel("rule_template")).toBe("Strukturvorlage")
    expect(generationLabel(null)).toBe("Herkunft nicht verifiziert")
  })

  it("jede Herkunft hat einen eigenen visuellen Ton", () => {
    const tones = Object.values(GENERATION_KIND_BADGE_CLASS)
    expect(new Set(tones).size).toBe(tones.length)
  })
})
