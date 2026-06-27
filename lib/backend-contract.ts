// Stabiler DTO-Contract zwischen UI und FastAPI-Bridge.
// Die UI rät keine Pydantic-Feldnamen: Die Bridge liefert exakt diese Shapes
// (camelCase, deutsche Step-/Feld-Labels bereits serverseitig aufbereitet).
// Änderungen hier sind Contract-Änderungen und müssen mit der Bridge
// abgestimmt werden.

import type { AnalyseSettings, DataClass, IntakeFormData } from "./types"

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

/**
 * Body von POST /runs: Der komplette Projektkontext reist mit dem Run —
 * die Beta ist zustandsarm, das Backend setzt die Datenklasse pro Lauf
 * unveränderlich und erzwingt die Policy serverseitig erneut.
 */
export interface RunStartRequestDto {
  intake: IntakeFormData
  settings: AnalyseSettings
  effectiveDataClass: DataClass
}

export interface RunStepDto {
  id: string
  /** Deutsches Klartext-Label des Schritts. */
  label: string
  state: "done" | "running" | "pending"
  /** Optionaler technischer Backend-Node-Name (nur Diagnose). */
  node?: string
}

export interface RunCostDto {
  usedChf: number
  limitChf: number
  /** true, wenn usedChf eine Schätzung ist (Mock/Vorab-Schätzung). */
  estimated?: boolean
}

export interface IssueCountsDto {
  blocker: number
  warning: number
  info: number
}

// Canonical contract RunStatus (run_state_v1_1.yaml). Presentational UI states
// are mapped separately (see app/quellen/page.tsx).
export type RunStatus =
  | "created"
  | "running"
  | "paused_for_review"
  | "completed"
  | "stopped"
  | "failed"
  | "cancelled"

export interface RunStatusDto {
  runId: string
  status: RunStatus
  /** Bevorzugte Quelle für das Fortschritts-Banner. */
  steps?: RunStepDto[]
  /** Fallback, wenn steps fehlen: aktueller Backend-Node. */
  currentNode?: string | null
  cost?: RunCostDto
  stopReason?: "cost_limit" | "user" | "error"
  /** Nur wenn true zeigt die UI einen Fortsetzen-Button. */
  canResume?: boolean
  issueCounts?: IssueCountsDto
  /** Vom Backend berechnete effektive Datenklasse des Laufs. */
  effectiveDataClass?: DataClass
}

// ---------------------------------------------------------------------------
// Felder, Belege, Issues (Review)
// ---------------------------------------------------------------------------

export interface EvidenceAnchorDto {
  anchorId: string
  sourceTitle: string
  location: string
  verified: boolean
}

export type IssueSeverity = "blocker" | "warning" | "info"
export type IssueState = "open" | "confirmed" | "overridden"

// Canonical user-facing severity wording. Single source so screens don't drift.
export const ISSUE_SEVERITY_LABELS: Record<IssueSeverity, string> = {
  blocker: "Blockierend",
  warning: "Warnung",
  info: "Hinweis",
}

export interface IssueDto {
  id: string
  fieldId: string
  severity: IssueSeverity
  title: string
  description: string
  evidence?: EvidenceAnchorDto[]
  state: IssueState
  overrideComment?: string
  overriddenBy?: string
}

export type FieldDraftStatus = "ready" | "needs_review" | "blocked"

export interface PortalFieldDraftDto {
  fieldId: string
  name: string
  text: string
  /** null = kein Portallimit für dieses Feld ("Kein Limit"). */
  charLimit: number | null
  status: FieldDraftStatus
  evidence: EvidenceAnchorDto[]
}

export interface GateRowDto {
  id: string
  label: string
  status: "passed" | "partial" | "failed"
  /** Kurzes Ergebnis in Klartext. */
  result: string
  /** Erklärtext im aufgeklappten Zustand. */
  detail: string
  /** true, wenn das Ergebnis aus einem unvollständigen Durchlauf stammt. */
  stale?: boolean
}

export interface RunFieldsDto {
  runId: string
  fields: PortalFieldDraftDto[]
  issues: IssueDto[]
  /** Qualitätsprüfungen; fehlt das Feld, leitet die UI sie aus den Issues ab. */
  gates?: GateRowDto[]
}

// ---------------------------------------------------------------------------
// Review-Entscheidungen
// ---------------------------------------------------------------------------

export interface ReviewDecisionDto {
  decisions: Array<{
    issueId: string
    action: "confirm" | "override"
    /** Pflicht bei action === "override". */
    comment?: string
  }>
  fieldEdits?: Array<{ fieldId: string; text: string }>
}

// ---------------------------------------------------------------------------
// Export — ein Pfad: GET /runs/{id}/export?kind= liefert das Binary direkt
// (Content-Disposition gesetzt). Es gibt kein POST /exports und kein
// Export-Status-Objekt im Contract.
// ---------------------------------------------------------------------------

export type ExportKind = "word" | "markdown" | "json_audit"

// ---------------------------------------------------------------------------
// Beta-Feedback (keine personenbezogenen Daten)
// ---------------------------------------------------------------------------

export type FeedbackScale = 1 | 2 | 3 | 4 | 5

export interface FeedbackDto {
  verstaendlichkeit: FeedbackScale
  nuetzlichkeit: FeedbackScale
  vertrauenBelege: FeedbackScale
  hitlAufwand: FeedbackScale
  hilfreich: string
  verbessern: string
}
