// R6 — Unterabschnitts-Gliederung über dem Composite-Text (kein Datenmodell-
// Split): Markererkennung, Status je Unterabschnitt, Teiltext-Extraktion.
import { describe, expect, it } from "vitest"

import {
  buildOutline,
  replaceSegmentBody,
  segmentParts,
  subsectionSpans,
  subsectionText,
} from "@/lib/subsections"

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

// Vollständiger Composite-Text: alle Registry-Marker genau einmal, in Reihenfolge.
const FULL_SUBS = [
  { marker: "4.1", label: "4.1 State of the art" },
  { marker: "4.2", label: "4.2 Novelty" },
  { marker: "4.5.1", label: "4.5.1 Patent search" },
]

const FULL_TEXT = [
  "4.1 State of the art",
  "Bestehende Verfahren und deren Grenzen.",
  "",
  "4.2 Novelty",
  "[[Angabe ergänzen: Antwort fachlich ergänzen]]",
  "",
  "4.5.1 Patent search",
  "Recherche abgeschlossen.",
].join("\n")

describe("subsectionSpans / segmentParts / replaceSegmentBody", () => {
  it("liefert exakte, lückenlose Spans in Registry-Reihenfolge", () => {
    const spans = subsectionSpans(FULL_TEXT, FULL_SUBS)
    expect(spans).not.toBeNull()
    expect(spans!.map((s) => s.marker)).toEqual(["4.1", "4.2", "4.5.1"])
    expect(spans![0].start).toBe(0)
    expect(spans![2].end).toBe(FULL_TEXT.length)
    // Lückenlos: jedes Span-Ende ist der Start des nächsten.
    expect(spans![0].end).toBe(spans![1].start)
    expect(spans![1].end).toBe(spans![2].start)
  })

  it("Round-Trip: slice → replace ergibt den zeichenidentischen Volltext", () => {
    const spans = subsectionSpans(FULL_TEXT, FULL_SUBS)!
    for (const span of spans) {
      const parts = segmentParts(FULL_TEXT, span)
      const body = FULL_TEXT.slice(parts.bodyStart, parts.end)
      expect(replaceSegmentBody(FULL_TEXT, span, body)).toBe(FULL_TEXT)
    }
  })

  it("ersetzt nur den Antwortbereich; Heading und Nachbarsegmente bleiben", () => {
    const spans = subsectionSpans(FULL_TEXT, FULL_SUBS)!
    const replaced = replaceSegmentBody(
      FULL_TEXT,
      spans[1],
      "Neue Antwort zu 4.2.\n\n"
    )
    expect(replaced).toContain("4.2 Novelty\nNeue Antwort zu 4.2.")
    expect(replaced).not.toContain("[[Angabe ergänzen")
    expect(replaced).toContain("4.1 State of the art\nBestehende Verfahren")
    expect(replaced).toContain("4.5.1 Patent search\nRecherche abgeschlossen.")
  })

  it("fail-closed: fehlender, doppelter oder umgeordneter Marker ⇒ null", () => {
    expect(subsectionSpans("4.1 nur dieser", FULL_SUBS)).toBeNull() // 4.2/4.5.1 fehlen
    expect(
      subsectionSpans("4.1 a\n4.2 b\n4.2 nochmal\n4.5.1 c", FULL_SUBS)
    ).toBeNull() // doppelt
    expect(
      subsectionSpans("4.2 zuerst\n4.1 danach\n4.5.1 c", FULL_SUBS)
    ).toBeNull() // außer Reihenfolge
    expect(subsectionSpans(FULL_TEXT, [])).toBeNull() // keine Subsections
  })

  it("erkennt Marker mit #-Heading-Präfix (Backend-Parität)", () => {
    const text = "## 4.1 State of the art\nInhalt.\n### 4.2 Novelty\nMehr.\n4.5.1 P\nx"
    const spans = subsectionSpans(text, FULL_SUBS)
    expect(spans).not.toBeNull()
    expect(spans!.map((s) => s.marker)).toEqual(["4.1", "4.2", "4.5.1"])
  })

  it("verwechselt 4.5 nicht mit 4.5.1 (Span-Ebene)", () => {
    const text = "4.5 IP-Überblick\nText.\n4.5.1 Patent search\nMehr."
    const spans = subsectionSpans(text, [
      { marker: "4.5", label: "4.5 IP" },
      { marker: "4.5.1", label: "4.5.1 Patent search" },
    ])
    expect(spans).not.toBeNull()
    expect(spans![0].end).toBe(spans![1].start)
  })

  it("segmentParts: Markerzeile ohne Body ⇒ leerer Antwortbereich", () => {
    const text = "4.1 Nur Heading"
    const spans = subsectionSpans(text, [FULL_SUBS[0]])!
    const parts = segmentParts(text, spans[0])
    expect(parts.bodyStart).toBe(parts.end)
    expect(replaceSegmentBody(text, spans[0], "")).toBe(text)
  })
})
