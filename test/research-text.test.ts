import { describe, expect, it } from "vitest"

import {
  normalizeResearchText,
  parseSearchTags,
  unicodeLength,
} from "@/lib/research-text"


describe("research text normalization", () => {
  it("uses NFC and trims only outer whitespace", () => {
    const input = "  KI-gestützte  Datenanalyse für Schweizer KMU – Zürich/DACH (B2B)  "
    expect(normalizeResearchText(input)).toBe(
      "KI-gestützte  Datenanalyse für Schweizer KMU – Zürich/DACH (B2B)"
    )
  })

  it("counts Unicode code points instead of UTF-16 units", () => {
    expect(unicodeLength("A😀ß")).toBe(3)
  })

  it("commits and deduplicates tags without changing inner punctuation", () => {
    expect(parseSearchTags(" Zürich/DACH (B2B), KI – Analyse, zürich/dach (b2b) ")).toEqual([
      "Zürich/DACH (B2B)",
      "KI – Analyse",
    ])
  })
})
