// C2 — Diff-Klassifikation: beibehalten / entfernt / hinzugefügt / umformuliert.
import { describe, expect, it } from "vitest"

import { applySegments, countChanges, diffSuggestion } from "@/lib/diff"

describe("diffSuggestion", () => {
  it("identische Texte ⇒ alles beibehalten", () => {
    const segments = diffSuggestion("Erster Satz. Zweiter Satz.", "Erster Satz. Zweiter Satz.")
    expect(segments.map((s) => s.kind)).toEqual(["beibehalten", "beibehalten"])
    expect(countChanges(segments)).toBe(0)
  })

  it("reine Ergänzung ⇒ hinzugefügt", () => {
    const segments = diffSuggestion(
      "Das Verfahren ist etabliert.",
      "Das Verfahren ist etabliert. Es senkt die Kosten deutlich."
    )
    expect(segments.map((s) => s.kind)).toEqual(["beibehalten", "hinzugefuegt"])
    expect(segments[1].after).toBe("Es senkt die Kosten deutlich.")
    expect(segments[1].before).toBeNull()
  })

  it("reine Streichung ⇒ entfernt", () => {
    const segments = diffSuggestion(
      "Kernaussage bleibt. Diese Wiederholung fliegt raus.",
      "Kernaussage bleibt."
    )
    expect(segments.map((s) => s.kind)).toEqual(["beibehalten", "entfernt"])
    expect(segments[1].before).toBe("Diese Wiederholung fliegt raus.")
    expect(segments[1].after).toBeNull()
  })

  it("hohe Wort-Überlappung ⇒ umformuliert mit Wort-Inner-Diff", () => {
    const segments = diffSuggestion(
      "Die Genauigkeit des Verfahrens beträgt 95 Prozent im Labor.",
      "Die Genauigkeit des Verfahrens beträgt voraussichtlich 95 Prozent im Feldtest."
    )
    expect(segments).toHaveLength(1)
    expect(segments[0].kind).toBe("umformuliert")
    const words = segments[0].words ?? []
    expect(words.some((w) => w.kind === "hinzugefuegt" && /voraussichtlich/.test(w.text))).toBe(true)
    expect(words.some((w) => w.kind === "entfernt" && /Labor/.test(w.text))).toBe(true)
    expect(words.some((w) => w.kind === "gleich" && /Genauigkeit/.test(w.text))).toBe(true)
  })

  it("geringe Überlappung ⇒ getrennt entfernt + hinzugefügt", () => {
    const segments = diffSuggestion(
      "Der Markt wächst stark.",
      "Unsere Partnerschaft deckt die Wertschöpfungskette ab."
    )
    expect(segments.map((s) => s.kind).sort((a, b) => a.localeCompare(b))).toEqual([
      "entfernt",
      "hinzugefuegt",
    ])
  })

  it("Leertexte sind kein Sonderfall", () => {
    expect(diffSuggestion("", "")).toEqual([])
    expect(diffSuggestion("", "Neuer Satz.").map((s) => s.kind)).toEqual(["hinzugefuegt"])
    expect(diffSuggestion("Alter Satz.", "").map((s) => s.kind)).toEqual(["entfernt"])
  })

  it("applySegments: übernimmt nur die gewählten Änderungen, Rest bleibt exakt", () => {
    const current = "4.2 Neuheit\nSatz eins bleibt.\nSatz zwei fliegt raus. Satz drei alt formuliert."
    const suggested =
      "4.2 Neuheit\nSatz eins bleibt.\nSatz drei neu formuliert. Ganz neuer Schlusssatz."
    const segments = diffSuggestion(current, suggested)
    const changeIndices = segments
      .map((s, i) => ({ s, i }))
      .filter(({ s }) => s.kind !== "beibehalten")

    // Nur die Umformulierung übernehmen: Streichung + Neusatz bleiben aus.
    const rephrased = changeIndices.find(({ s }) => s.kind === "umformuliert")!
    const partial = applySegments(current, segments, new Set([rephrased.i]))
    expect(partial).toContain("Satz drei neu formuliert.")
    expect(partial).toContain("Satz zwei fliegt raus.")
    expect(partial).not.toContain("Ganz neuer Schlusssatz.")
    expect(partial.startsWith("4.2 Neuheit\nSatz eins bleibt.\n")).toBe(true)

    // Alle Änderungen ⇒ inhaltlich der Vorschlag (Struktur bleibt erhalten).
    const all = applySegments(current, segments, new Set(changeIndices.map(({ i }) => i)))
    expect(all).toContain("Satz drei neu formuliert.")
    expect(all).toContain("Ganz neuer Schlusssatz.")
    expect(all).not.toContain("fliegt raus")
    expect(all.startsWith("4.2 Neuheit\nSatz eins bleibt.\n")).toBe(true)

    // Keine Auswahl ⇒ zeichenidentischer Ausgangstext.
    expect(applySegments(current, segments, new Set())).toBe(current)
  })

  it("25k-Zeichen-Smoke: bleibt schnell und korrekt", () => {
    const base = Array.from({ length: 250 }, (_, i) => `Satz Nummer ${i} beschreibt Detail ${i}.`)
    const changed = [...base]
    changed[100] = "Satz Nummer 100 beschreibt das überarbeitete Detail 100."
    const started = performance.now()
    const segments = diffSuggestion(base.join(" "), changed.join(" "))
    expect(performance.now() - started).toBeLessThan(2000)
    expect(segments.filter((s) => s.kind !== "beibehalten")).toHaveLength(1)
    expect(segments.find((s) => s.kind === "umformuliert")).toBeTruthy()
  })
})
