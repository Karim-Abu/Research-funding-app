// Requirements client (live v1.1 slice). listRequirements returns the
// run-scoped RequirementAssessments produced by the deterministic precheck.

import type { EvidenceLinkDto } from "./evidence"

export type RequirementStatus =
  | "fulfilled"
  | "partial"
  | "open"
  | "needs_input"
  | "blocked"
export type AssessmentBasis =
  | "deterministic_rule"
  | "semantic_assessment"
  | "hybrid"
  | "human_override"
export type IssueSeverity = "blocker" | "warning" | "info"
// RUN 2A Slice 1 (additiv): offene/bestätigte menschliche Prüfung als separate
// Dimension — ändert den Compliance-Status nie. Guidance-Hinweise (severity
// info in der Registry) zählen in keiner Quote und werden getrennt angezeigt.
export type ReviewStatus = "not_required" | "required" | "confirmed"
export type DisplayMode = "requirement" | "guidance"

export interface OpenIssueDto {
  issue_id: string
  run_id: string
  issue_type: string
  severity: IssueSeverity
  description: string
  target_type: string
  target_id: string
  recommended_next_action: string
  status: "open" | "resolved" | "overridden" | "dismissed"
  responsible_user_id?: string | null
  created_at: string
}

export interface RuleEvidenceDto {
  rule_id: string
  registry_version: string
  source_ref: string
  source_title: string
  source_url?: string | null
  source_path?: string | null
  last_verified?: string | null
  evidence_quote: string
  evidence_label: "Kuratierter Registry-Auszug"
}

export interface RequirementAssessmentDto {
  assessment_id: string
  requirement_id: string
  title?: string | null
  status: RequirementStatus
  basis: AssessmentBasis
  reasoning: string
  stale: boolean
  evidence_links: EvidenceLinkDto[]
  open_issues: OpenIssueDto[]
  // Additive (Slice 4): registry-declared portal fields this requirement affects.
  affected_field_ids?: string[]
  // Additive (RUN 2A Slice 1): separate Review-Dimension + Guidance-Anzeige.
  review_status?: ReviewStatus
  display_mode?: DisplayMode
  rule_evidence?: RuleEvidenceDto[]
}

export const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  not_required: "Keine Bestätigung nötig",
  required: "Menschliche Bestätigung offen",
  confirmed: "Menschlich bestätigt",
}

// German user-facing labels (RUN 4A status catalog). `open` heisst bewusst
// «Prüfung nötig», nicht «Nicht erfüllt»: das Backend nutzt `open` auch für
// «menschliche Entscheidung nötig» und «semantisch nicht bewertet»
// (backend/app/rules/aggregation.py) — nur `blocked` ist eine verletzte Regel.
export const STATUS_LABELS: Record<RequirementStatus, string> = {
  fulfilled: "Erfüllt",
  partial: "Teilweise erfüllt",
  open: "Prüfung nötig",
  needs_input: "Nicht beurteilbar",
  blocked: "Nicht erfüllt",
}

// Kurzbegründung je Status — im Detailbereich neben dem Label gerendert.
export const STATUS_REASONS: Record<RequirementStatus, string> = {
  fulfilled: "Die maschinelle Prüfung ist bestanden.",
  partial: "Ein Teil der notwendigen Angaben fehlt.",
  open: "Nicht maschinell entscheidbar — eine Person muss diesen Punkt prüfen.",
  needs_input: "Erforderliche Daten fehlen.",
  blocked: "Die Regel ist verletzt.",
}

export const BASIS_LABELS: Record<AssessmentBasis, string> = {
  deterministic_rule: "Regelbasiert",
  semantic_assessment: "Inhaltliche Prüfung",
  hybrid: "Regel + menschliche Bestätigung",
  human_override: "Manuell entschieden",
}

export const STALE_NOTICE =
  "Projektangaben wurden seit dieser Prüfung geändert. Starten Sie die Prüfung erneut."

export async function listRequirements(
  runId: string
): Promise<RequirementAssessmentDto[]> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/requirements`
  )
  if (!res.ok) {
    throw new Error(
      res.status === 404
        ? "Die Prüfung wurde nicht gefunden."
        : "Die Anforderungen konnten nicht geladen werden."
    )
  }
  return (await res.json()) as RequirementAssessmentDto[]
}
