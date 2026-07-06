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
}

// German user-facing labels (recommended in the milestone spec).
export const STATUS_LABELS: Record<RequirementStatus, string> = {
  fulfilled: "Erfüllt",
  partial: "Teilweise erfüllt",
  open: "Offen",
  needs_input: "Angaben nötig",
  blocked: "Blockiert",
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
