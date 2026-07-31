// R6 Unterabschnitts-Gliederung für Composite-Felder (3.1–3.3, 4.1–4.6 inkl.
// 4.5.1–4.5.4). Die Marker kommen aus der Registry (Portal-Fields-Katalog,
// `subsections`); dieser Helper erkennt sie im bestehenden Composite-Text.
// Reine UI-Gliederung — kein Datenmodell-Split: der kopierte Portaltext bleibt
// der zusammengesetzte Composite-Text.

import { hasPlaceholder } from "@/lib/draft-view"

export interface SubsectionDef {
  marker: string // "3.1", "4.5.1"
  label: string // Registry-Frage, z. B. "3.1 Describe the business targets …"
}

export type SubsectionState = "vorhanden" | "fehlt" | "platzhalter"

export interface OutlineEntry extends SubsectionDef {
  state: SubsectionState
  /** Zeichenposition der Markerzeile im Text (−1 wenn nicht gefunden). */
  index: number
}

const escape = (marker: string) => marker.replaceAll(".", String.raw`\.`)

/** Position der Markerzeile ("4.5.1 …" am Zeilenanfang), oder −1. */
function markerIndex(text: string, marker: string): number {
  const re = new RegExp(`^[ \\t]*${escape(marker)}(?![.\\d])`, "m")
  const match = re.exec(text)
  return match ? match.index : -1
}

/**
 * Gliederung des Composite-Texts entlang der Registry-Marker. Ein
 * Unterabschnitt ist "vorhanden", wenn seine Markerzeile existiert und danach
 * inhaltlicher Text folgt; "platzhalter", wenn der Abschnitt Platzhalter
 * enthält; sonst "fehlt".
 */
export function buildOutline(text: string, subsections: SubsectionDef[]): OutlineEntry[] {
  const positions = subsections.map((sub) => ({
    ...sub,
    index: markerIndex(text, sub.marker),
  }))
  const sortedFound = positions
    .filter((p) => p.index >= 0)
    .sort((a, b) => a.index - b.index)

  return positions.map((sub) => {
    if (sub.index < 0) return { ...sub, state: "fehlt", index: -1 }
    const next = sortedFound.find((p) => p.index > sub.index)
    const body = text.slice(sub.index, next ? next.index : undefined)
    // Inhalt = Abschnittstext ohne den führenden Marker-Token.
    const content = body
      .replace(new RegExp(`^[ \\t]*${escape(sub.marker)}[.:)\\s-]*`), "")
      .trim()
    if (content === "") return { ...sub, state: "fehlt", index: sub.index }
    if (hasPlaceholder(body)) return { ...sub, state: "platzhalter", index: sub.index }
    return { ...sub, state: "vorhanden", index: sub.index }
  })
}

/** Teiltext eines Unterabschnitts (für "Unterabschnitt kopieren"), oder null. */
export function subsectionText(
  text: string,
  subsections: SubsectionDef[],
  marker: string
): string | null {
  const outline = buildOutline(text, subsections)
  const entry = outline.find((e) => e.marker === marker)
  if (!entry || entry.index < 0) return null
  const next = outline
    .filter((e) => e.index > entry.index)
    .sort((a, b) => a.index - b.index)[0]
  return text.slice(entry.index, next ? next.index : undefined).trimEnd()
}

/**
 * Inhalt eines Unterabschnitts ohne Markerzeile/-token (Spiegel der
 * Backend-Erkennung in field_drafting_context._section_is_initial_draft):
 * die Registry-Frage als Überschrift zählt nicht als Inhalt
 * (Vorlagenzustand), Anwendertext auf der Markerzeile schon. Null, wenn der
 * Marker im Text fehlt.
 */
export function subsectionContent(
  text: string,
  subsections: SubsectionDef[],
  marker: string
): string | null {
  const slice = subsectionText(text, subsections, marker)
  if (slice === null) return null
  const def = subsections.find((s) => s.marker === marker)
  const lines = slice.split("\n")
  if (def && lines[0]?.trim() === def.label.trim()) {
    return lines.slice(1).join("\n")
  }
  lines[0] = (lines[0] ?? "").replace(
    new RegExp(`^[ \\t]*(?:#{1,6}[ \\t]+)?${escape(marker)}[.:)\\s-]*`),
    ""
  )
  return lines.join("\n")
}

export const SUBSECTION_STATE_LABELS: Record<SubsectionState, string> = {
  vorhanden: "Vorhanden",
  platzhalter: "Platzhalter offen",
  fehlt: "Fehlt noch",
}

// ---------------------------------------------------------------------------
// Exakte Segment-Spans für die editierbare Fokusansicht (B1–B4).
//
// Identische Semantik wie backend/app/drafts/sections.py::section_spans —
// dieselbe Marker-Regex (inkl. optionalem #-Heading-Präfix), genau EIN
// Treffer je Registry-Marker, Registry-Reihenfolge; sonst fail-closed (null,
// die UI degradiert zum Ein-Block-Editor). Anders als `subsectionText`
// (trimEnd, Anzeige/Kopieren) arbeiten diese Helper mit exakten Slices:
// slice → replace ergibt zeichenidentischen Volltext (Round-Trip).
// ---------------------------------------------------------------------------

export interface SubsectionSpan {
  marker: string
  start: number
  end: number
}

function spanPattern(marker: string): RegExp {
  return new RegExp(
    `^[ \\t]*(?:#{1,6}[ \\t]+)?${escape(marker)}(?![.\\d])`,
    "gm"
  )
}

export function subsectionSpans(
  text: string,
  subsections: SubsectionDef[]
): SubsectionSpan[] | null {
  if (subsections.length === 0) return null
  const starts: { marker: string; start: number }[] = []
  for (const sub of subsections) {
    const matches = [...text.matchAll(spanPattern(sub.marker))]
    if (matches.length !== 1) return null
    starts.push({ marker: sub.marker, start: matches[0].index })
  }
  for (let i = 1; i < starts.length; i++) {
    if (starts[i].start <= starts[i - 1].start) return null
  }
  return starts.map((entry, index) => ({
    marker: entry.marker,
    start: entry.start,
    end: index + 1 < starts.length ? starts[index + 1].start : text.length,
  }))
}

export interface SegmentParts {
  /** Start der Markerzeile (== span.start) — die Portalfrage. */
  headingStart: number
  /** Erste Position nach der Markerzeile — der editierbare Antwortbereich. */
  bodyStart: number
  end: number
}

export function segmentParts(text: string, span: SubsectionSpan): SegmentParts {
  const newline = text.indexOf("\n", span.start)
  const bodyStart = newline >= 0 && newline < span.end ? newline + 1 : span.end
  return { headingStart: span.start, bodyStart, end: span.end }
}

/** Ersetzt exakt den Antwortbereich eines Segments — Heading und alle übrigen
 *  Segmente bleiben zeichenidentisch erhalten. */
export function replaceSegmentBody(
  text: string,
  span: SubsectionSpan,
  newBody: string
): string {
  const parts = segmentParts(text, span)
  return text.slice(0, parts.bodyStart) + newBody + text.slice(parts.end)
}
