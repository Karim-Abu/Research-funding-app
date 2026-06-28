// Presentation helpers for the Anforderungen / Fördervoraussetzungen screen.
// Pure functions over the existing shapes (live RequirementAssessmentDto and the
// mock Requirement). No backend calls, no contract changes.

import type { RequirementStatus } from "./requirements"
import type { MachineStatus } from "./types"

// ---------------------------------------------------------------------------
// User-friendly fallbacks — never show raw ids/enums.
// ---------------------------------------------------------------------------
export const REQ_FALLBACK = {
  title: "Unbenannte Anforderung",
  category: "Weitere Anforderungen",
  evidence: "Noch kein Beleg verknüpft",
  portal: "Kein Portal-Feld zugeordnet",
  human: "Noch nicht menschlich geprüft",
} as const

// ---------------------------------------------------------------------------
// Status buckets — one canonical 4-state model for summary + filtering.
// "Erfüllt" refers to the requirement (not evidence verification).
// ---------------------------------------------------------------------------
export type ReqBucket = "fulfilled" | "partial" | "open" | "blocked"

export const REQ_BUCKET_LABELS: Record<ReqBucket, string> = {
  fulfilled: "Erfüllt",
  partial: "Teilweise",
  open: "Offen",
  blocked: "Blocker",
}

export const REQ_BUCKET_STYLE: Record<ReqBucket, { chip: string; text: string }> = {
  fulfilled: {
    chip: "bg-status-fulfilled/12 text-status-fulfilled",
    text: "text-status-fulfilled",
  },
  partial: {
    chip: "bg-status-partial/12 text-status-partial",
    text: "text-status-partial",
  },
  open: { chip: "bg-muted text-muted-foreground", text: "text-muted-foreground" },
  blocked: {
    chip: "bg-destructive/10 text-destructive",
    text: "text-destructive",
  },
}

/** Live RequirementStatus → bucket (needs_input folds into "open"). */
export function liveStatusToBucket(status: RequirementStatus): ReqBucket {
  switch (status) {
    case "fulfilled":
      return "fulfilled"
    case "partial":
      return "partial"
    case "blocked":
      return "blocked"
    case "open":
    case "needs_input":
      return "open"
  }
}

/** Mock MachineStatus → bucket. */
export function machineStatusToBucket(status: MachineStatus): ReqBucket {
  switch (status) {
    case "verified":
      return "fulfilled"
    case "partial":
      return "partial"
    case "blocker":
      return "blocked"
    case "open":
      return "open"
  }
}

// ---------------------------------------------------------------------------
// Evidence + human review state (requirement-level, user-facing wording).
// ---------------------------------------------------------------------------
export type EvidenceState = "confirmed" | "present" | "missing"
export const EVIDENCE_STATE_LABELS: Record<EvidenceState, string> = {
  confirmed: "Fundstelle bestätigt",
  present: "Beleg vorhanden",
  missing: REQ_FALLBACK.evidence,
}

export type HumanState = "confirmed" | "needed" | "not_required"
export const HUMAN_STATE_LABELS: Record<HumanState, string> = {
  confirmed: "Menschlich bestätigt",
  needed: "Menschliche Prüfung nötig",
  not_required: "Nicht nötig",
}

// ---------------------------------------------------------------------------
// Filters (frontend-only state).
// ---------------------------------------------------------------------------
export type ReqFilter =
  | "all"
  | "blocked"
  | "partial"
  | "open"
  | "human_needed"
  | "no_evidence"

export const REQ_FILTER_ORDER: ReqFilter[] = [
  "all",
  "blocked",
  "partial",
  "open",
  "human_needed",
  "no_evidence",
]

export const REQ_FILTER_LABELS: Record<ReqFilter, string> = {
  all: "Alle",
  blocked: "Blocker",
  partial: "Teilweise",
  open: "Offen",
  human_needed: "Menschliche Prüfung nötig",
  no_evidence: "Ohne Beleg",
}

/** The minimal normalized view both screens map onto for filtering + counting. */
export interface ReqView {
  bucket: ReqBucket
  humanState: HumanState
  evidenceState: EvidenceState
}

export function matchesFilter(v: ReqView, filter: ReqFilter): boolean {
  switch (filter) {
    case "all":
      return true
    case "blocked":
      return v.bucket === "blocked"
    case "partial":
      return v.bucket === "partial"
    case "open":
      return v.bucket === "open"
    case "human_needed":
      return v.humanState === "needed"
    case "no_evidence":
      return v.evidenceState === "missing"
  }
}

export interface ReqSummary {
  fulfilled: number
  partial: number
  open: number
  blocked: number
  humanNeeded: number
  noEvidence: number
}

export function summarize(views: ReqView[]): ReqSummary {
  return {
    fulfilled: views.filter((v) => v.bucket === "fulfilled").length,
    partial: views.filter((v) => v.bucket === "partial").length,
    open: views.filter((v) => v.bucket === "open").length,
    blocked: views.filter((v) => v.bucket === "blocked").length,
    humanNeeded: views.filter((v) => v.humanState === "needed").length,
    noEvidence: views.filter((v) => v.evidenceState === "missing").length,
  }
}

// ---------------------------------------------------------------------------
// Live categorisation — derive a readable group from the requirement id, since
// the contract carries no portal category. Heuristic, with a clean fallback.
// ---------------------------------------------------------------------------
export const REQ_CATEGORY_ORDER: string[] = [
  "Fördervoraussetzungen / Eligibility",
  "Budget & Beiträge",
  "Organisation & Partner",
  "Value Creation",
  "Solution / Innovation",
  "Project Setup",
  "Summary & Submit",
  REQ_FALLBACK.category,
]

export function categorize(requirementId: string): string {
  const id = requirementId.toUpperCase()
  if (/ELIG|FUND|FOERDER|FÖRDER/.test(id)) return "Fördervoraussetzungen / Eligibility"
  if (/BUDGET|COST|KOST|FINANC|BEITRAG/.test(id)) return "Budget & Beiträge"
  if (/PARTNER|\bORG\b|ROLE|PEOPLE|TEAM/.test(id)) return "Organisation & Partner"
  if (/VALUE|\bVC\b|MARKET|MARKT|WERT/.test(id)) return "Value Creation"
  if (/\bSOL\b|SOLUTION|TECH|INNO/.test(id)) return "Solution / Innovation"
  if (/\bPS\b|PROJECT|SETUP|PLAN|TIMELINE|MILESTONE/.test(id)) return "Project Setup"
  if (/SUMMARY|SUBMIT|ABSTRACT|INTRO/.test(id)) return "Summary & Submit"
  return REQ_FALLBACK.category
}
