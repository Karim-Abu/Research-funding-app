// Innolink transfer helpers (Milestone 8.1): registry-order grouping, placeholder
// detection, per-field copy warnings, and the unsupported-area coverage list.
// Pure functions over existing DTOs — no new API, no backend.

import type { CopyReadiness, PortalFieldDraftDto } from "./fields"
import { hasPlaceholder } from "./placeholders"
import type { ReviewPackageDto } from "./review"
import { getCsrfToken } from "./session"

export { countPlaceholders, hasPlaceholder } from "./placeholders"

// Canonical Innolink portal sections (field-id prefix → label). Mirrors the
// editor's section map; the field ORDER comes from listFields (registry order),
// not re-sorted here.
export const SECTION_LABELS: Record<string, string> = {
  INTRO: "Einleitung",
  ORG: "Organisation & Partner",
  VC: "Wertschöpfung",
  SOL: "Lösung & Innovation",
  PS: "Projektplan",
  SUM: "Summary & Submit",
}
export const SECTION_ORDER = ["INTRO", "ORG", "VC", "SOL", "PS", "SUM"] as const

export function sectionKey(fieldId: string): string {
  return fieldId.split(".")[0]
}

export function sectionLabel(fieldId: string): string {
  return SECTION_LABELS[sectionKey(fieldId)] ?? "Weitere"
}

export function isComposite(fieldId: string): boolean {
  return fieldId.endsWith(".EDITOR")
}

export interface FieldGroup {
  key: string
  label: string
  fields: PortalFieldDraftDto[]
}

/** Group supported fields by section, preserving the incoming (registry) order. */
export function groupBySection(fields: PortalFieldDraftDto[]): FieldGroup[] {
  const groups: FieldGroup[] = []
  for (const field of fields) {
    const key = sectionKey(field.field_id)
    let group = groups.find((g) => g.key === key)
    if (!group) {
      group = { key, label: SECTION_LABELS[key] ?? "Weitere", fields: [] }
      groups.push(group)
    }
    group.fields.push(field)
  }
  // Keep the canonical section order for the headers.
  return groups.sort(
    (a, b) =>
      (SECTION_ORDER.indexOf(a.key as never) + 1 || 99) -
      (SECTION_ORDER.indexOf(b.key as never) + 1 || 99)
  )
}

// ---------------------------------------------------------------------------
// R6 Copy-Readiness — Backend leitet ab, hier wird NUR gerendert. Bewusst nie
// "einreichbereit": copy_ready heisst "bereit zum Kopieren" (Arbeitsstand).
// ---------------------------------------------------------------------------
export const COPY_READINESS_LABELS: Record<CopyReadiness, string> = {
  copy_ready: "Bereit zum Kopieren",
  draft: "Arbeitskopie",
  placeholders_open: "Platzhalter offen",
  not_reviewed: "Prüfung nicht aktuell",
  blocker: "Blocker",
}

export const COPY_READINESS_STYLE: Record<CopyReadiness, string> = {
  copy_ready: "bg-status-fulfilled/12 text-status-fulfilled",
  draft: "bg-muted text-muted-foreground",
  placeholders_open: "bg-status-partial/12 text-status-partial",
  not_reviewed: "bg-status-partial/12 text-status-partial",
  blocker: "bg-status-blocker/12 text-status-blocker",
}

/** Backend-Wert bevorzugt; Anzeige-Fallback aus den Warnungen (Mock-Modus /
 * ältere Antworten) — spiegelt die Backend-Präzedenz, nie "copy_ready" ohne
 * aktuelle Freigabe. */
export function fieldCopyReadiness(
  field: PortalFieldDraftDto,
  review: ReviewPackageDto | null
): CopyReadiness {
  if (field.copy_readiness) return field.copy_readiness
  const warnings = fieldWarnings(field, review)
  const codes = new Set(warnings.map((w) => w.code))
  if (codes.has("limit")) return "blocker"
  if (codes.has("open")) return "placeholders_open"
  if (codes.has("review")) return "not_reviewed"
  if (review?.approval_status === "approved" && !review.recheck_required) {
    return "copy_ready"
  }
  return "draft"
}

// ---------------------------------------------------------------------------
// R6 Kapitel-/Gesamt-Kopie: Client-seitige Assemblierung in Registry-Reihen-
// folge. Feldüberschriften sind Orientierung für die Arbeitskopie — der
// Portaltext je Feld bleibt der reine Feldtext (Feld-Kopie bleibt "nur Text").
// ---------------------------------------------------------------------------
export function assembleChapterText(group: FieldGroup): string {
  const parts = group.fields.map(
    (field) => `${field.field_name}\n${field.current_version.text.trim()}`
  )
  return [group.label, ...parts].join("\n\n")
}

export function assembleFullDraftText(fields: PortalFieldDraftDto[]): string {
  return groupBySection(fields)
    .map((group) => assembleChapterText(group))
    .join("\n\n\n")
}

export type WarningCode = "open" | "limit" | "review"

export interface CopyWarning {
  code: WarningCode
  message: string
}

/** Active copy warnings for a field. Review warnings require a ReviewPackage
 * (absent in mock mode). Copy is never blocked — these are advisory. */
export function fieldWarnings(
  field: PortalFieldDraftDto,
  review: ReviewPackageDto | null
): CopyWarning[] {
  const warnings: CopyWarning[] = []
  const text = field.current_version.text

  if (hasPlaceholder(text) || field.open_issue_count > 0) {
    warnings.push({ code: "open", message: "Dieser Feldtext enthält noch offene Angaben." })
  }
  if (field.character_limit != null && field.character_count > field.character_limit) {
    warnings.push({
      code: "limit",
      message: "Der Text überschreitet das Innolink-Zeichenlimit.",
    })
  }
  if (review) {
    const blocker = review.findings.some(
      (f) => f.field_id === field.field_id && f.severity === "blocker" && f.status === "open"
    )
    // Mit Backend-Copy-Readiness ist DIESE die kanonische Freigabe-Aussage
    // (kennt auch Feld-Freigaben); sonst wie bisher die Lauf-Freigabe.
    const approvalNotCurrent = field.copy_readiness
      ? field.copy_readiness !== "copy_ready"
      : review.recheck_required || review.approval_status !== "approved"
    if (approvalNotCurrent || blocker) {
      warnings.push({ code: "review", message: "Die Prüfungs-Freigabe ist nicht aktuell." })
    }
  }
  return warnings
}

// Structured / repeated portal areas the Beta does NOT cover — entered directly
// in Innolink. Static (structural, not project content).
export const UNSUPPORTED_AREAS = [
  "Arbeitspakete (Work Packages)",
  "Meilensteine",
  "Partner-Stundentabellen",
  "Budget- und Finanzierungsplan",
  "Lohnkosten-Tabellen",
  "Materialkosten-Positionen",
  "Eigenleistungs-/Bar-Beiträge",
  "Datei-Uploads",
  "Checkbox-/Dropdown-Auswahlen ohne Entwurfstext",
] as const

export const COVERAGE_STATEMENT =
  "Die Übernahmeansicht deckt derzeit die unterstützten Textfelder ab. " +
  "Strukturierte und wiederholbare Portalbereiche müssen weiterhin direkt in " +
  "Innolink erfasst werden."

export const CLIPBOARD_PRIVACY_NOTE =
  "Hinweis: Kopierte Inhalte liegen in der Zwischenablage Ihres Geräts und " +
  "können dort von anderen lokalen Anwendungen gelesen werden."

export type StructuredCopyTarget =
  | "partner_row"
  | "partner_cell"
  | "budget_value"
  | "duration"

export interface TransferPartnerDto {
  index: number
  name: string
  partner_type: string
  partner_type_label?: string
  project_role: string
  country: string
  swiss_value_creation: boolean | null
  eligibility_status: string
  eligibility_status_label?: string
  provenance: string
  copy_target_row: string
}

export interface TransferSnapshotDto {
  snapshot_available: boolean
  stale: boolean
  stale_message: string | null
  project: {
    title?: string
    instrument?: string
    duration_months?: number | null
    duration_copy_target?: string
    application_language?: null
  }
  partners: TransferPartnerDto[]
  budget: {
    values: Array<{ key: string; label: string; value: number | null; copy_target: string; provenance: string }>
    ratios: Array<{ label: string; value: number }>
    rules: Array<{ rule_id: string; status: string; status_label?: string; outcome_label: string; severity: string }>
  }
  sources: Array<{ source_id: string; title: string; url: string | null }>
  manual_portal_tasks: string[]
}

export async function getTransferSnapshot(runId: string): Promise<TransferSnapshotDto> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/transfer-snapshot`)
  if (!res.ok) throw new Error("Strukturierte Übernahmedaten konnten nicht geladen werden.")
  return (await res.json()) as TransferSnapshotDto
}

export async function recordStructuredCopyEvent(
  runId: string,
  targetType: StructuredCopyTarget,
  targetKey: string
): Promise<void> {
  const csrf = getCsrfToken()
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/transfer-copy-events`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
    // No structured text/value is sent. The backend resolves it from the frozen snapshot.
    body: JSON.stringify({ target_type: targetType, target_key: targetKey }),
  })
  if (!res.ok) throw new Error("Kopierversuch konnte nicht protokolliert werden.")
}
