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
  portal: "Keinem konkreten Portalfeld zugeordnet",
  human: "Menschliche Prüfung offen",
  relevance: "Diese Anforderung beeinflusst die Vollständigkeit oder Prüfbarkeit des Antrags.",
} as const

// ---------------------------------------------------------------------------
// Status buckets — one canonical 4-state model for summary + filtering.
// "Erfüllt" refers to the requirement (not evidence verification).
// ---------------------------------------------------------------------------
export type ReqBucket = "fulfilled" | "partial" | "open" | "blocked"

export const REQ_BUCKET_LABELS: Record<ReqBucket, string> = {
  fulfilled: "Erfüllt",
  partial: "Teilweise erfüllt",
  open: "Offen",
  blocked: "Blocker",
}

// Short, non-technical explanations for the summary tiles. Rendered via an
// accessible trigger (click/focus, not hover-only) — see StatusHelp.
export const REQ_TILE_HELP = {
  fulfilled:
    "Das System hat für diesen Punkt ausreichende Angaben oder Belege gefunden. Die menschliche Prüfung bleibt massgebend.",
  partial:
    "Es liegen Angaben oder Belege vor, aber sie decken den Punkt noch nicht vollständig ab.",
  open: "Dieser Punkt wurde noch nicht bearbeitet oder es fehlen Angaben.",
  blocked:
    "Dieser Punkt verhindert aktuell die Freigabe oder Einreichungsreife des Entwurfs.",
  humanNeeded:
    "Das System hat einen Befund erstellt, aber eine Person muss ihn bestätigen oder korrigieren.",
  noEvidence:
    "Die Aussage ist noch nicht mit einer Quelle verknüpft. Ergänzen Sie einen Beleg oder schwächen Sie die Aussage ab.",
} as const

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
  needed: "Menschliche Prüfung offen",
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
  partial: "Teilweise erfüllt",
  open: "Offen",
  human_needed: "Menschliche Prüfung offen",
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

// ---------------------------------------------------------------------------
// "Warum relevant?" — category-derived, honest one-liners (the contract has no
// per-requirement relevance field). Generic fallback in REQ_FALLBACK.relevance.
// ---------------------------------------------------------------------------
const CATEGORY_RELEVANCE: Record<string, string> = {
  "Fördervoraussetzungen / Eligibility":
    "Ohne erfüllte Fördervoraussetzungen kann das Projekt nicht als Innosuisse-Innovationsprojekt eingereicht werden.",
  "Budget & Beiträge":
    "Budget und Beiträge müssen plausibel sein, damit der Antrag geprüft werden kann.",
  "Organisation & Partner":
    "Ein Innovationsprojekt braucht typischerweise einen beitragsberechtigten Schweizer Forschungspartner und einen Umsetzungspartner.",
}

export function relevanceFor(category: string): string {
  return CATEGORY_RELEVANCE[category] ?? REQ_FALLBACK.relevance
}

// ---------------------------------------------------------------------------
// Primary action per requirement — one clear CTA depending on the problem.
// Routing confidence is tiered (never keyword-first):
//   1. explicit view-model signals (evidence state)
//   2. recommended_next_action texts from open_issues
//   3. known requirement-id types of the beta profile
//   4. title keywords as last fallback
// When unsure, route neutrally to the Qualitätsprüfung instead of guessing.
// ---------------------------------------------------------------------------
export interface ReqAction {
  label: string
  href: string
}

export const REQ_NEUTRAL_ACTION: ReqAction = {
  label: "In Qualitätsprüfung öffnen",
  href: "/review",
}

const PARTNER_ACTION: ReqAction = { label: "Im Intake Partner ergänzen", href: "/intake" }
const BUDGET_ACTION: ReqAction = { label: "Im Intake Budget ergänzen", href: "/intake" }
const DRAFT_ACTION: ReqAction = { label: "Im Entwurf bearbeiten", href: "/editor" }
const SOURCE_ACTION: ReqAction = { label: "Quelle ergänzen", href: "/quellen" }

const PARTNER_RE = /forschungspartner|umsetzungspartner|partner/i
const BUDGET_RE = /budget|barbeitrag|beitrag|kosten|finanzierung|chf/i
const DRAFT_RE = /platzhalter|entwurf|feldtext|portalfeld|ausfüllen|ergänzen sie.*(feld|text)/i
const SOURCE_RE = /quelle|beleg|evidenz|fundstelle|nachweis/i

export function primaryActionFor(v: {
  requirementId: string
  title: string
  bucket: ReqBucket
  evidenceState: EvidenceState
  humanState: HumanState
  firstAnchorId: string | null
  /** recommended_next_action / description texts from open_issues. */
  openPoints: string[]
}): ReqAction | null {
  // Fulfilled requirements need no corrective action.
  if (v.bucket === "fulfilled") {
    return v.firstAnchorId
      ? {
          label: "Beleg ansehen",
          href: `/quellen?tab=evidenz&anchor=${encodeURIComponent(v.firstAnchorId)}`,
        }
      : null
  }

  // 1. Explicit view-model signal: missing evidence is unambiguous.
  if (v.evidenceState === "missing") return SOURCE_ACTION

  // 2. Structured hint from the contract: recommended next actions.
  const hints = v.openPoints.join(" ")
  if (hints) {
    if (PARTNER_RE.test(hints)) return PARTNER_ACTION
    if (BUDGET_RE.test(hints)) return BUDGET_ACTION
    if (SOURCE_RE.test(hints)) return SOURCE_ACTION
    if (DRAFT_RE.test(hints)) return DRAFT_ACTION
  }

  // 3. Known requirement-id types of the beta profile.
  const id = v.requirementId.toUpperCase()
  if (/PARTNER/.test(id)) return PARTNER_ACTION
  if (/BUDGET|COST|KOST|FINANC|BEITRAG/.test(id)) return BUDGET_ACTION

  // 4. Title keywords — last, weakest signal.
  if (PARTNER_RE.test(v.title)) return PARTNER_ACTION
  if (BUDGET_RE.test(v.title)) return BUDGET_ACTION

  // Unsure → neutral: confirm/clarify in the Qualitätsprüfung.
  return REQ_NEUTRAL_ACTION
}
