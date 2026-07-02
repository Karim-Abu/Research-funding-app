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
  field: "Keine direkte Feldzuordnung",
  status: "Noch nicht geprüft",
  evidence: "Noch kein Beleg verknüpft",
  noReview: "Noch keine Qualitätsprüfung durchgeführt",
} as const

export const HUMAN_IN_THE_LOOP_NOTE =
  "Die Qualitätsprüfung unterstützt die fachliche Kontrolle. Die finale Entscheidung bleibt beim Menschen."

// ---------------------------------------------------------------------------
// KI-gestützte Hinweise (A3 evidence-consistency findings, Milestone 9G).
// Advisory only; surfaced separately from the deterministic checks. We identify
// them by profile_id and never show model/provider/confidence.
// ---------------------------------------------------------------------------
export const AI_FINDINGS_LABEL = "KI-gestützte Hinweise"
export const AI_FINDINGS_DESCRIPTION =
  "Hinweise einer KI-Prüfung zu Belegen und Konsistenz. Vorschläge zur menschlichen Prüfung — keine Freigabe."

/** A finding produced by an A3 review agent (profile_id like "A3.…"). */
export function isAiFinding(finding: ReviewFindingDto): boolean {
  return (finding.profile_id ?? "").startsWith("A3.")
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

/** The deterministic (non-AI) findings — fed to the quality-check groups. */
export function deterministicFindings(pkg: ReviewPackageDto): ReviewFindingDto[] {
  return pkg.findings.filter((f) => !isAiFinding(f))
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
// Quality-check groups — stable set, derived from the findings by keyword.
// ---------------------------------------------------------------------------
export type ReviewGroupKey =
  | "pflichtfelder"
  | "zeichenlimits"
  | "platzhalter"
  | "belege"
  | "anforderungen"
  | "konsistenz"
  | "budget"
  | "export"

export const REVIEW_GROUP_ORDER: ReviewGroupKey[] = [
  "pflichtfelder",
  "zeichenlimits",
  "platzhalter",
  "belege",
  "anforderungen",
  "konsistenz",
  "budget",
  "export",
]

export const REVIEW_GROUP_LABELS: Record<ReviewGroupKey, string> = {
  pflichtfelder: "Pflichtfelder",
  zeichenlimits: "Zeichenlimits",
  platzhalter: "Platzhalter",
  belege: "Belege & Fundstellen",
  anforderungen: "Anforderungen",
  konsistenz: "Konsistenz",
  budget: "Budget & Beiträge",
  export: "Exportbereitschaft",
}

export const REVIEW_GROUP_DESCRIPTIONS: Record<ReviewGroupKey, string> = {
  pflichtfelder: "Sind alle Pflichtfelder ausgefüllt?",
  zeichenlimits: "Halten die Texte die Innolink-Zeichenlimits ein?",
  platzhalter: "Enthalten Felder noch offene Platzhalter?",
  belege: "Sind Aussagen mit Belegen hinterlegt?",
  anforderungen: "Sind die Fördervoraussetzungen erfüllt?",
  konsistenz: "Sind die Angaben in sich stimmig?",
  budget: "Sind Budget und Beiträge plausibel?",
  export: "Ist der Antrag bereit für den Export?",
}

/** Map a finding onto a quality-check group via keywords (with a calm fallback). */
export function classifyFinding(finding: ReviewFindingDto): ReviewGroupKey {
  const text = `${finding.description} ${finding.field_id ?? ""} ${finding.requirement_id ?? ""}`.toLowerCase()
  if (/platzhalter|placeholder|\[\[|\btbd\b|\btodo\b|angabe ergänzen/.test(text)) return "platzhalter"
  if (/zeichen|limit|character|länge|gekürzt|zu lang/.test(text)) return "zeichenlimits"
  if (/beleg|evidenz|fundstelle|quelle|source/.test(text)) return "belege"
  if (/budget|kost|finanz|beitrag/.test(text)) return "budget"
  if (/export|innolink|portal|abgabe/.test(text)) return "export"
  if (/anforderung|requirement|voraussetzung|eligib|partner/.test(text)) return "anforderungen"
  if (/pflichtfeld|mandatory|required|fehlt|nicht ausgefüllt|leer|ausstehend/.test(text)) return "pflichtfelder"
  return "konsistenz"
}

export type GroupStatus = "bestanden" | "teilweise" | "nicht_bestanden"

export const GROUP_STATUS_LABELS: Record<GroupStatus, string> = {
  bestanden: "Bestanden",
  teilweise: "Teilweise",
  nicht_bestanden: "Nicht bestanden",
}

export const GROUP_STATUS_STYLE: Record<GroupStatus, string> = {
  bestanden: "bg-status-fulfilled/12 text-status-fulfilled",
  teilweise: "bg-status-partial/12 text-status-partial",
  nicht_bestanden: "bg-destructive/10 text-destructive",
}

export interface ReviewGroup {
  key: ReviewGroupKey
  label: string
  description: string
  status: GroupStatus
  findings: ReviewFindingDto[]
}

function groupStatus(findings: ReviewFindingDto[]): GroupStatus {
  if (findings.some((f) => f.severity === "blocker")) return "nicht_bestanden"
  if (findings.length > 0) return "teilweise"
  return "bestanden"
}

/** Build the full, ordered group set. Groups without findings count as passed. */
export function groupFindings(findings: ReviewFindingDto[]): ReviewGroup[] {
  return REVIEW_GROUP_ORDER.map((key) => {
    const groupFinds = findings.filter((f) => classifyFinding(f) === key)
    return {
      key,
      label: REVIEW_GROUP_LABELS[key],
      description: REVIEW_GROUP_DESCRIPTIONS[key],
      status: groupStatus(groupFinds),
      findings: groupFinds,
    }
  })
}

// ---------------------------------------------------------------------------
// Summary counts shown above the screen.
// ---------------------------------------------------------------------------
export interface ReviewSummary {
  bestanden: number
  teilweise: number
  nichtBestanden: number
  blocker: number
  hinweise: number
  pruefungNoetig: number
}

export function summarizeReview(pkg: ReviewPackageDto): ReviewSummary {
  const groups = groupFindings(pkg.findings)
  const blockerFindings = pkg.findings.filter((f) => f.severity === "blocker").length
  const hintFindings = pkg.findings.filter((f) => f.severity !== "blocker").length
  const pruefungNoetig = pkg.requirements.filter(
    (r) =>
      r.basis !== "human_override" &&
      (r.status === "partial" || r.status === "needs_input" || r.status === "open")
  ).length
  return {
    bestanden: groups.filter((g) => g.status === "bestanden").length,
    teilweise: groups.filter((g) => g.status === "teilweise").length,
    nichtBestanden: groups.filter((g) => g.status === "nicht_bestanden").length,
    blocker: pkg.blocker_count || blockerFindings,
    hinweise: pkg.warning_count || hintFindings,
    pruefungNoetig,
  }
}

// Extra counters for the approval/blocker panel.
export interface BlockerBreakdown {
  blocker: number
  placeholderFields: number
  missingEvidence: number
  openMandatory: number
}

export function blockerBreakdown(pkg: ReviewPackageDto): BlockerBreakdown {
  const byGroup = (key: ReviewGroupKey) =>
    pkg.findings.filter((f) => f.severity === "blocker" && classifyFinding(f) === key).length
  return {
    blocker: pkg.blocker_count || pkg.findings.filter((f) => f.severity === "blocker").length,
    placeholderFields: byGroup("platzhalter"),
    missingEvidence: byGroup("belege"),
    openMandatory: byGroup("pflichtfelder"),
  }
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
  const last = parts[parts.length - 1] ?? id
  return `${section} → ${humanizeSegment(last)}`
}

// ---------------------------------------------------------------------------
// Deduplicate identical hints into "N × …".
// ---------------------------------------------------------------------------
export interface DedupedFinding {
  description: string
  count: number
  findings: ReviewFindingDto[]
}

export function dedupeFindings(findings: ReviewFindingDto[]): DedupedFinding[] {
  const map = new Map<string, DedupedFinding>()
  for (const f of findings) {
    const key = f.description.trim() || REVIEW_FALLBACKS.title
    const entry = map.get(key)
    if (entry) {
      entry.count += 1
      entry.findings.push(f)
    } else {
      map.set(key, { description: key, count: 1, findings: [f] })
    }
  }
  return [...map.values()]
}

/** Why a blocker matters — short, group-aware sentence (no debug wording). */
export function blockerRelevance(finding: ReviewFindingDto): string {
  switch (classifyFinding(finding)) {
    case "platzhalter":
      return "Dieses Pflichtfeld kann nicht exportiert werden, solange Platzhalter enthalten sind."
    case "pflichtfelder":
      return "Pflichtfelder müssen vor Export oder Freigabe vollständig ausgefüllt sein."
    case "zeichenlimits":
      return "Der Text überschreitet das Innolink-Zeichenlimit und muss gekürzt werden."
    case "belege":
      return "Ohne hinterlegten Beleg kann diese Aussage nicht bestätigt werden."
    case "budget":
      return "Budgetangaben müssen plausibel und vollständig sein."
    default:
      return "Dieser Punkt verhindert die Freigabe und den Export."
  }
}
