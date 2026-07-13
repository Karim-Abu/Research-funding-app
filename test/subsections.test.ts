// R6 — Unterabschnitts-Gliederung über dem Composite-Text (kein Datenmodell-
// Split): Markererkennung, Status je Unterabschnitt, Teiltext-Extraktion.
import { describe, expect, it } from "vitest"

import { buildOutline, subsectionText } from "@/lib/subsections"

const SOL_SUBS = [
  { marker: "4.1", label: "4.1 State of the art" },
  { marker: "4.2", label: "4.2 Novelty" },
  { marker: "4.5.1", label: "4.5.1 Patent search" },
  { marker: "4.5.2", label: "4.5.2 Freedom to operate" },
]

const TEXT = [
  "4.1 Stand der Technik: bestehende Verfahren und deren Grenzen.",
  "Weitere Details zur Ausgangslage.",
  "4.5.1 Patentrecherche: Ergebnisse als [[Angabe ergänzen: Trefferliste]].",
  "4.5.2",
].join("\n")

describe("buildOutline", () => {
  it("erkennt vorhandene, fehlende und Platzhalter-Unterabschnitte", () => {
    const outline = buildOutline(TEXT, SOL_SUBS)
    const byMarker = Object.fromEntries(outline.map((e) => [e.marker, e.state]))
    expect(byMarker["4.1"]).toBe("vorhanden")
    expect(byMarker["4.2"]).toBe("fehlt") // Marker kommt nicht vor
    expect(byMarker["4.5.1"]).toBe("platzhalter")
    expect(byMarker["4.5.2"]).toBe("fehlt") // Markerzeile ohne Inhalt
  })

  it("verwechselt 4.5 nicht mit 4.5.1 (Marker-Grenzen)", () => {
    const outline = buildOutline("4.5.1 Inhalt vorhanden.", [
      { marker: "4.5", label: "4.5 IP" },
      { marker: "4.5.1", label: "4.5.1 Patent search" },
    ])
    expect(outline.find((e) => e.marker === "4.5")?.state).toBe("fehlt")
    expect(outline.find((e) => e.marker === "4.5.1")?.state).toBe("vorhanden")
  })

  it("behält die Registry-Reihenfolge unabhängig von der Textreihenfolge", () => {
    const text = "4.2 Neuheit zuerst.\n4.1 Stand der Technik danach."
    const outline = buildOutline(text, SOL_SUBS)
    expect(outline.map((e) => e.marker)).toEqual(["4.1", "4.2", "4.5.1", "4.5.2"])
  })
})

describe("subsectionText", () => {
  it("extrahiert den Teiltext bis zum nächsten Marker", () => {
    const part = subsectionText(TEXT, SOL_SUBS, "4.1")
    expect(part).toContain("4.1 Stand der Technik")
    expect(part).toContain("Weitere Details")
    expect(part).not.toContain("4.5.1")
  })

  it("liefert null für nicht gefundene Marker", () => {
    expect(subsectionText(TEXT, SOL_SUBS, "4.2")).toBeNull()
  })
})
