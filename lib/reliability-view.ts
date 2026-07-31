// View-Model der sichtbaren Qualitätsprüfung: übersetzt die technischen
// Reliability-Findings (M9K) in konkrete, nicht-technische Prüfpunkte
// («9 Markt- und Wettbewerbsangaben brauchen einen Beleg.»).
//
// Rechnet nichts neu und interpretiert keine Domänenfakten um: gruppiert nur
// nach Finding-Familie, zählt und wählt die Klartext-Formulierung. Die
// Fachbegriffe und Kennzahlen bleiben unverändert in den technischen
// Prüfinformationen der Karte erhalten (verlagert, nicht gelöscht).

import type { ReliabilityFindingDto } from "./reliability"

/** Ein Prüfpunkt der Standardansicht: eine Problemart mit Anzahl. */
export interface CheckpointGroup {
  /** Finding-Familie bzw. «other» — nie sichtbar, nur Schlüssel/Testanker. */
  family: string
  count: number
  /** Klartextsatz inklusive Anzahl. */
  text: string
  /** true nur, wenn diese Punkte Export/Freigabe tatsächlich blockieren. */
  critical: boolean
}

/** Familie eines Finding-Codes («reliability:market:clm-7» → «reliability:market»). */
export function findingFamily(code: string): string {
  return code.split(":").slice(0, 2).join(":")
}

type Phrase = (count: number) => string

// Klartext je Familie. Keine Prüfbegriffe («Suffizienz», «Konsensrisiko»,
// «Drift»), keine Aussage über inhaltliche Wahrheit — immer eine Aufgabe.
const CHECKPOINT_TEXT: Record<string, Phrase> = {
  "reliability:conflict": (n) =>
    n === 1
      ? "1 Angabe widerspricht der verknüpften Quelle."
      : `${n} Angaben widersprechen den verknüpften Quellen.`,
  "reliability:unsupported": (n) =>
    n === 1
      ? "1 Stelle braucht noch einen Beleg."
      : `${n} Stellen brauchen noch einen Beleg.`,
  "reliability:weak": (n) =>
    n === 1
      ? "Bei 1 Stelle reicht der Beleg noch nicht aus."
      : `Bei ${n} Stellen reicht der Beleg noch nicht aus.`,
  "reliability:market": (n) =>
    n === 1
      ? "1 Markt- oder Wettbewerbsangabe braucht einen Beleg."
      : `${n} Markt- und Wettbewerbsangaben brauchen einen Beleg.`,
  "reliability:proposed_fact": (n) =>
    n === 1
      ? "1 KI-Vorschlag wurde noch nicht bestätigt."
      : `${n} KI-Vorschläge wurden noch nicht bestätigt.`,
  "reliability:quantified": (n) =>
    n === 1
      ? "1 Zahl stimmt noch nicht eindeutig mit der Quelle überein."
      : `${n} Zahlen stimmen noch nicht eindeutig mit den Quellen überein.`,
  "reliability:false_consensus": (n) =>
    n === 1
      ? "1 KI-Formulierung ist noch nicht belegt."
      : `${n} KI-Formulierungen sind noch nicht belegt.`,
  "reliability:drift": (n) =>
    n === 1
      ? "1 Formulierung sagt mehr aus als der Beleg."
      : `${n} Formulierungen sagen mehr aus als die Belege.`,
}

const OTHER_TEXT: Phrase = (n) =>
  n === 1
    ? "1 weitere Stelle braucht eine Prüfung."
    : `${n} weitere Stellen brauchen eine Prüfung.`

/** Anzeigereihenfolge bei gleicher Kritikalität und gleicher Anzahl. */
const FAMILY_ORDER = [
  "reliability:conflict",
  "reliability:market",
  "reliability:quantified",
  "reliability:proposed_fact",
  "reliability:unsupported",
  "reliability:false_consensus",
  "reliability:weak",
  "reliability:drift",
  "other",
]

// «reliability:stale» ist kein inhaltlicher Prüfpunkt, sondern der Zustand
// «Ergebnis veraltet» — er hat in der Karte seinen eigenen Status.
const NOT_A_CHECKPOINT = new Set(["reliability:stale"])

/** Gruppiert offene Findings zu Prüfpunkten: kritische zuerst, dann die
 *  grösseren Gruppen. Unbekannte Familien landen gesammelt in «other», damit
 *  keine Meldung stillschweigend verschwindet. */
export function checkpointGroups(
  findings: ReliabilityFindingDto[]
): CheckpointGroup[] {
  const groups = new Map<string, { count: number; critical: boolean }>()
  for (const finding of findings) {
    const family = findingFamily(finding.finding_code)
    if (NOT_A_CHECKPOINT.has(family)) continue
    const key = family in CHECKPOINT_TEXT ? family : "other"
    const entry = groups.get(key) ?? { count: 0, critical: false }
    entry.count += 1
    entry.critical = entry.critical || finding.severity === "blocker"
    groups.set(key, entry)
  }
  return [...groups.entries()]
    .map(([family, { count, critical }]) => ({
      family,
      count,
      critical,
      text: (CHECKPOINT_TEXT[family] ?? OTHER_TEXT)(count),
    }))
    .sort(
      (a, b) =>
        Number(b.critical) - Number(a.critical) ||
        b.count - a.count ||
        FAMILY_ORDER.indexOf(a.family) - FAMILY_ORDER.indexOf(b.family)
    )
}

/** Ehrliche Einordnung der Prüfpunkte — bleibt in der Standardansicht sichtbar. */
export const CHECKPOINT_SCOPE_NOTE =
  "Prüfpunkte sind Hinweise für die menschliche Prüfung — kein Fehler der " +
  "Anwendung und keine Aussage zur Förderwahrscheinlichkeit."
