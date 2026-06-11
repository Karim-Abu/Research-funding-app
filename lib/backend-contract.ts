// Stabiler DTO-Contract zwischen UI und FastAPI-Bridge.
// Die UI rät keine Pydantic-Feldnamen: Die Bridge liefert exakt diese Shapes
// (camelCase, deutsche Step-/Feld-Labels bereits serverseitig aufbereitet).
// Änderungen hier sind Contract-Änderungen und müssen mit der Bridge
// abgestimmt werden.

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

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

export type RunStatus = "running" | "completed" | "stopped" | "failed"

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
  charLimit: number
  status: FieldDraftStatus
  evidence: EvidenceAnchorDto[]
}

export interface RunFieldsDto {
  runId: string
  fields: PortalFieldDraftDto[]
  issues: IssueDto[]
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
// Export
// ---------------------------------------------------------------------------

export type ExportKind = "word" | "markdown" | "json_audit"

export interface ExportDto {
  exportId: string
  kind: ExportKind
  status: "generating" | "ready" | "error"
  filename?: string
}

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
