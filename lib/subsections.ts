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

export const SUBSECTION_STATE_LABELS: Record<SubsectionState, string> = {
  vorhanden: "Vorhanden",
  platzhalter: "Platzhalter offen",
  fehlt: "Fehlt noch",
}
