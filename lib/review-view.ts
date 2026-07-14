// Presentation helpers for the Qualitätsprüfung (review) screen. Pure functions
// over the existing ReviewPackageDto — no backend calls, no contract changes.

import type {
  FindingSeverity,
  ReviewFindingDto,
  ReviewPackageDto,
} from "./review"

// ---------------------------------------------------------------------------
// Fallbacks — never show raw ids/enums/undefined.
// ---------------------------------------------------------------------------
export const REVIEW_FALLBACKS = {
  title: "Unbenannter Prüfbefund",
  field: "Keinem konkreten Portalfeld zugeordnet",
  status: "Noch nicht geprüft",
  evidence: "Noch kein Beleg verknüpft",
  noReview: "Noch keine Qualitätsprüfung durchgeführt",
} as const

export const HUMAN_IN_THE_LOOP_NOTE =
  "Die Qualitätsprüfung unterstützt die fachliche Kontrolle. Die finale Entscheidung bleibt beim Menschen."

// Progress framing — the summary shows work/check progress, never a funding
// likelihood. Shown directly under the summary tiles.
export const REVIEW_PROGRESS_NOTE =
  "Bearbeitungs- und Prüfstand — keine Aussage zur Förderwahrscheinlichkeit."

// Clarifies that completing the review is an internal step, not a submission.
export const APPROVAL_SCOPE_NOTE =
  "Diese Freigabe bestätigt nur die interne Prüfung. Der Antrag wird nicht eingereicht."

// Short, non-technical explanations for the summary legend. Rendered via an
// accessible trigger (click/focus, not hover-only) — see StatusHelp.
export const REVIEW_TILE_HELP = {
  bestanden:
    "Prüfbereiche, deren Check ausgeführt wurde und keine offenen Befunde hat. Das ist eine Systemprüfung — keine menschliche Freigabe.",
  teilweise:
    "Prüfbereiche mit Hinweisen, aber ohne blockierende Befunde.",
  nichtBestanden:
    "Prüfbereiche mit mindestens einem blockierenden Befund.",
  nichtGeprueft:
    "Prüfbereiche, deren Check noch nicht oder nicht auf dem aktuellen Stand ausgeführt wurde. Ohne ausgeführten Check gilt ein Bereich nie als bestanden.",
  blockierendeAufgaben:
    "Gruppierte Aufgaben, die Freigabe und Export verhindern, bis sie geklärt sind.",
  evidenzhinweise:
    "Technische Zahl der einzelnen Evidenzhinweise hinter den gruppierten Aufgaben. Sie blockieren nicht automatisch.",
  pruefungNoetig:
    "Anforderungen, bei denen eine Person den Systembefund bestätigen oder Angaben ergänzen muss.",
} as const

// ---------------------------------------------------------------------------
// Advisory A3 findings. Neutral wording avoids implying a model call when a
// legacy/demo finding has no verified generation provenance.
// Advisory only; surfaced separately from the deterministic checks. We identify
// them by profile_id and never show model/provider/confidence.
// ---------------------------------------------------------------------------
export const AI_FINDINGS_LABEL = "Fachliche Prüfhinweise"
export const AI_FINDINGS_DESCRIPTION =
  "Hinweise einer KI-Prüfung zu Belegen und Konsistenz. Vorschläge zur menschlichen Prüfung — keine Freigabe."

/** A finding produced by an A3 review agent (profile_id like "A3.…"). */
export function isAiFinding(finding: ReviewFindingDto): boolean {
  return (finding.profile_id ?? "").startsWith("A3.")
}

// ---------------------------------------------------------------------------
// Section-comment types (Entwurf → Kommentare). The contract has no comment
// type field, so the chosen type is stored as a visible prefix in the comment
// text itself ("[Frage] …") and parsed back for display. "Hinweis" is the
// default and stays unprefixed.
// ---------------------------------------------------------------------------
export const COMMENT_TYPES = ["Hinweis", "Frage", "Änderung nötig"] as const
export type CommentType = (typeof COMMENT_TYPES)[number]

const COMMENT_TYPE_RE = /^\[(Hinweis|Frage|Änderung nötig)\]\s*/

/** Prefix the comment text with the chosen type (default type stays plain). */
export function commentWithType(type: CommentType, text: string): string {
  return type === "Hinweis" ? text : `[${type}] ${text}`
}

/** Split a stored comment back into type badge + display text. */
export function parseCommentType(description: string): {
  type: CommentType | null
  text: string
} {
  const m = COMMENT_TYPE_RE.exec(description)
  if (!m) return { type: null, text: description }
  return { type: m[1] as CommentType, text: description.slice(m[0].length) }
}

// ---------------------------------------------------------------------------
// Reliability staleness (M10.1, audit F3). The backend surfaces a stale
// reliability pass as a run-level M9K blocker finding; claim-bound reliability
// findings always carry a field_id, so profile + missing field identifies it.
// ---------------------------------------------------------------------------
export const RELIABILITY_PROFILE_ID = "M9K.reliability_assurance"

export function reliabilityStaleFinding(
  pkg: ReviewPackageDto
): ReviewFindingDto | null {
  return (
    pkg.findings.find(
      (f) =>
        f.profile_id === RELIABILITY_PROFILE_ID &&
        !f.field_id &&
        f.status === "open" &&
        f.severity === "blocker"
    ) ?? null
  )
}

/** The advisory KI findings in a package, in their existing order. */
export function aiFindings(pkg: ReviewPackageDto): ReviewFindingDto[] {
  return pkg.findings.filter(isAiFinding)
}

// ---------------------------------------------------------------------------
// Severity labels + styles (review wording: Blocker / Hinweis).
// ---------------------------------------------------------------------------
export const REVIEW_SEVERITY_LABELS: Record<FindingSeverity, string> = {
  blocker: "Blocker",
  warning: "Hinweis",
  info: "Hinweis",
}

export const REVIEW_SEVERITY_STYLE: Record<FindingSeverity, string> = {
  blocker: "bg-destructive/10 text-destructive",
  warning: "bg-status-partial/12 text-status-partial",
  info: "bg-muted text-muted-foreground",
}

// ---------------------------------------------------------------------------
// Prüfbereichs-Status: Die frühere Keyword-Gruppierung mit automatischer
// Pass-Logik («leere Gruppe = bestanden») ist entfernt. Autoritative Quelle
// der neun Prüfbereiche ist ausschliesslich der Backend-View
// GET /review/check-status (lib/check-status.ts); die Aufgabenliste kommt aus
// der Fix Queue (lib/fix-queue.ts).
// ---------------------------------------------------------------------------

// Title help for the progress card — explicit non-funding framing.
export const PROGRESS_CARD_HELP =
  "Diese Anzeige beschreibt den Bearbeitungs- und Prüfstand. Sie ist keine Aussage zur Förderwahrscheinlichkeit."

/** Anforderungen, die eine menschliche Bestätigung/Angabe brauchen. */
export function humanReviewCount(pkg: ReviewPackageDto): number {
  return pkg.requirements.filter(
    (r) =>
      r.basis !== "human_override" &&
      (r.status === "partial" || r.status === "needs_input" || r.status === "open")
  ).length
}

// ---------------------------------------------------------------------------
// Field label — readable "Introduction → Abstract", never the raw id.
// ---------------------------------------------------------------------------
const REVIEW_SECTION_LABELS: Record<string, string> = {
  INTRO: "Introduction",
  ORG: "Organisations & People",
  VC: "Value Creation",
  SOL: "Solution",
  PS: "Project Setup",
  SUMMARY: "Summary & Submit",
}

function humanizeSegment(segment: string): string {
  const cleaned = segment.replace(/[_-]+/g, " ").trim().toLowerCase()
  return cleaned.replace(/\b\w/g, (c) => c.toUpperCase())
}

export function fieldLabel(fieldId?: string | null): string {
  const id = fieldId?.trim()
  if (!id) return REVIEW_FALLBACKS.field
  const parts = id.split(".")
  const section = REVIEW_SECTION_LABELS[parts[0]] ?? "Weitere Felder"
  // Das technische Schluss-Segment «EDITOR» ist kein Feldname (CLAUDEX:
  // «Open Editor» nie als sichtbarer Feldname) — das inhaltliche Segment
  // davor trägt den Namen («Business Targets Model»).
  let last = parts[parts.length - 1] ?? id
  if (/^editor$/i.test(last) && parts.length > 2) {
    last = parts[parts.length - 2]
  }
  return `${section} → ${humanizeSegment(last)}`
}

