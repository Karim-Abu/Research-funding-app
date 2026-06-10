// Dummy-Daten für den Prototyp. Keine echten Daten, keine Backend-Aufrufe.

import type { MachineStatus, HumanCheck } from "./types"

// ---------------------------------------------------------------------------
// Gate rows (Qualitätsprüfungen)
// ---------------------------------------------------------------------------

export type GateStatus = "passed" | "partial" | "failed"

export interface GateRow {
  id: string
  label: string
  status: GateStatus
  result: string
  detail: string
  jumpSection: string
  /** When true, renders the "Stand: unvollständiger Durchlauf" stale stamp */
  stale?: boolean
}

export const GATE_ROWS: GateRow[] = [
  {
    id: "g1",
    label: "Alle Pflichtfelder ausgefüllt",
    status: "passed",
    result: "Alle 24 Pflichtfelder sind ausgefüllt.",
    detail:
      "Die Prüfung hat alle Pflichtfelder im Antragsformular durchlaufen. Kein Feld ist leer oder enthält einen ungültigen Platzhalter.",
    jumpSection: "Intake",
  },
  {
    id: "g2",
    label: "Zeichenlimits eingehalten",
    status: "failed",
    result: "Abschnitt «Projektziel» überschreitet das Limit um 312 Zeichen.",
    detail:
      "Das Feld «Projektziel» erlaubt maximal 2 000 Zeichen. Der aktuelle Entwurf enthält 2 312 Zeichen. Kürzen Sie den Abschnitt oder verschieben Sie Details in den Anhang.",
    jumpSection: "Entwurf",
  },
  {
    id: "g3",
    label: "Belege für Kernaussagen vorhanden",
    status: "partial",
    result: "3 von 8 Kernaussagen ohne verknüpften Beleg.",
    detail:
      "Die Aussagen zu Marktgrösse, Innovationscharakter und Wettbewerbsdifferenzierung sind nicht mit einem Beleg aus den hochgeladenen Unterlagen verknüpft. Verknüpfen Sie die entsprechenden Belege im Evidenz-Bereich.",
    jumpSection: "Evidenz",
  },
  {
    id: "g4",
    label: "Budget im Rahmen",
    status: "passed",
    result: "Gesamtbudget liegt im zulässigen Förderrahmen.",
    detail:
      "Das beantragte Budget von CHF 482 000 (Dummy) liegt innerhalb des maximalen Förderrahmens von CHF 600 000 (Dummy). Die Budgetstruktur ist plausibel.",
    jumpSection: "Intake",
  },
  {
    id: "g5",
    label: "Keine Widersprüche erkannt",
    status: "partial",
    result: "Möglicher Widerspruch in Abschnitt «Zeitplan».",
    detail:
      "Das Startdatum im Zeitplan (März 2026) widerspricht dem im Intake angegebenen frühesten Projektbeginn (Juni 2026). Bitte prüfen und angleichen.",
    jumpSection: "Entwurf",
    stale: true,
  },
]

// ---------------------------------------------------------------------------
// Findings (Hinweise)
// ---------------------------------------------------------------------------

export type FindingSeverity = "blocker" | "important" | "hint"
export type FindingState = "open" | "resolved"

export interface Finding {
  id: string
  severity: FindingSeverity
  state: FindingState
  title: string
  description: string
  jumpSection: string
}

export const FINDINGS: Finding[] = [
  // 2 blockers
  {
    id: "f1",
    severity: "blocker",
    state: "open",
    title: "Zeichenlimit überschritten",
    description:
      "Abschnitt «Projektziel» ist 312 Zeichen zu lang. Freigabe nicht möglich, bis das Limit eingehalten wird.",
    jumpSection: "Entwurf",
  },
  {
    id: "f2",
    severity: "blocker",
    state: "open",
    title: "Pflichtangabe fehlt: Ethikvotum",
    description:
      "Das Förderformular verlangt ein gültiges Ethikvotum. Das Feld ist leer.",
    jumpSection: "Intake",
  },
  // 7 open findings (5 shown, 2 behind "Weitere anzeigen")
  {
    id: "f3",
    severity: "important",
    state: "open",
    title: "3 Kernaussagen ohne Beleg",
    description:
      "Marktgrösse, Innovationscharakter und Wettbewerbsdifferenzierung sind nicht belegt.",
    jumpSection: "Evidenz",
  },
  {
    id: "f4",
    severity: "important",
    state: "open",
    title: "Widerspruch im Zeitplan",
    description:
      "Startdatum im Zeitplan (März 2026) stimmt nicht mit dem Intake-Angabe (Juni 2026) überein.",
    jumpSection: "Entwurf",
  },
  {
    id: "f5",
    severity: "important",
    state: "open",
    title: "Budgetposten «Reisekosten» nicht begründet",
    description:
      "Reisekosten von CHF 18 000 (Dummy) sind im Finanzplan ohne Begründung aufgeführt.",
    jumpSection: "Entwurf",
  },
  {
    id: "f6",
    severity: "hint",
    state: "open",
    title: "Abstrakt enthält technischen Jargon",
    description:
      "Einige Begriffe im Abstract sind nicht für fachfremde Gutachter geeignet.",
    jumpSection: "Entwurf",
  },
  {
    id: "f7",
    severity: "hint",
    state: "open",
    title: "Partner-CVs nicht hochgeladen",
    description:
      "Für Umsetzungspartner «Innovatech AG» fehlt der CV-Anhang.",
    jumpSection: "Quellen",
  },
  // 2 more behind "Weitere Hinweise anzeigen (2)"
  {
    id: "f8",
    severity: "hint",
    state: "open",
    title: "Anhang «Referenzliste» fehlt",
    description:
      "Das Formular empfiehlt eine Referenzliste früherer Projekte. Diese ist nicht beigefügt.",
    jumpSection: "Quellen",
  },
  {
    id: "f9",
    severity: "hint",
    state: "open",
    title: "Beschreibung des Verwertungsplans sehr kurz",
    description:
      "Der Verwertungsplan hat aktuell 180 Zeichen. Gutachter erwarten mindestens 300 Zeichen.",
    jumpSection: "Entwurf",
  },
  // 3 resolved
  {
    id: "f10",
    severity: "important",
    state: "resolved",
    title: "Projektlaufzeit fehlte",
    description: "Die Projektlaufzeit war nicht angegeben.",
    jumpSection: "Intake",
  },
  {
    id: "f11",
    severity: "hint",
    state: "resolved",
    title: "Tippfehler im Projekttitel",
    description: "Der Projekttitel enthielt einen Tippfehler.",
    jumpSection: "Intake",
  },
  {
    id: "f12",
    severity: "hint",
    state: "resolved",
    title: "Fehlende Abkürzungserklärung",
    description: "Das Kürzel «FSLE» war im Text nicht erklärt.",
    jumpSection: "Entwurf",
  },
]

// ---------------------------------------------------------------------------
// Approval card state
// ---------------------------------------------------------------------------

export type ApprovalState =
  | "blocked"
  | "open"
  | "approved"
  | "stale"
  | "changes_requested"

export interface ApprovalData {
  state: ApprovalState
  approvedBy?: string
  approvedAt?: string
  changesRequestedBy?: string
  changesRequestedComment?: string
  selfReview?: boolean
}

export const DEFAULT_APPROVAL: ApprovalData = {
  state: "blocked",
  selfReview: true,
}

// ---------------------------------------------------------------------------
// Page scenario registry (for debug switcher)
// ---------------------------------------------------------------------------

export type PageScenario =
  | "default"
  | "all_clear"
  | "blocked"
  | "approved"
  | "stale"
  | "empty"
  | "stopped_run"
  | "changes_requested"

export interface ReviewScenario {
  id: PageScenario
  label: string
}

export const PAGE_SCENARIOS: ReviewScenario[] = [
  { id: "default", label: "Standard (Blocker)" },
  { id: "all_clear", label: "Alles OK" },
  { id: "approved", label: "Freigegeben" },
  { id: "stale", label: "Freigabe veraltet" },
  { id: "changes_requested", label: "Änderungen nötig" },
  { id: "empty", label: "Leer" },
  { id: "stopped_run", label: "Gestoppter Durchlauf" },
]
