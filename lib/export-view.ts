// Presentation helpers for the Export screen + Innolink copy view. Pure
// functions over existing DTOs — no backend calls, no contract changes.

import type { PortalFieldDraftDto } from "./fields"
import { hasPlaceholder } from "./portal-transfer"
import type { ReviewPackageDto } from "./review"

// ---------------------------------------------------------------------------
// User-friendly fallbacks — never show raw ids/enums/undefined.
// ---------------------------------------------------------------------------
export const EXPORT_FALLBACKS = {
  noText: "Für dieses Feld liegt noch kein Textentwurf vor.",
  noLimit: "Kein Zeichenlimit hinterlegt",
  noReview: "Noch nicht geprüft",
  noEvidence: "Noch keine Evidenz verknüpft",
  unnamedField: "Unbenanntes Feld",
  fallbackSection: "Weitere Felder",
} as const

// Calm reminder that nothing is transferred automatically.
export const NO_AUTO_SUBMIT_NOTE =
  "Hinweis: Die Inhalte werden nicht automatisch nach Innolink übertragen. Kopieren Sie geprüfte Texte manuell in das Portal und prüfen Sie sie vor der Einreichung."

// ---------------------------------------------------------------------------
// Review readiness shown in the status card.
// ---------------------------------------------------------------------------
export type ExportReviewStatus =
  | "bestanden"
  | "blockiert"
  | "veraltet"
  | "offen"
  | "nicht_durchgefuehrt"

export const EXPORT_REVIEW_LABELS: Record<ExportReviewStatus, string> = {
  bestanden: "Bestanden",
  blockiert: "Blockiert",
  veraltet: "Veraltet",
  offen: "Offen",
  nicht_durchgefuehrt: "Nicht durchgeführt",
}

export const EXPORT_REVIEW_STYLE: Record<ExportReviewStatus, string> = {
  bestanden: "bg-status-fulfilled/12 text-status-fulfilled",
  blockiert: "bg-destructive/10 text-destructive",
  veraltet: "bg-status-partial/12 text-status-partial",
  offen: "bg-muted text-muted-foreground",
  nicht_durchgefuehrt: "bg-muted text-muted-foreground",
}

export function exportReviewStatus(pkg: ReviewPackageDto | null): ExportReviewStatus {
  if (!pkg) return "nicht_durchgefuehrt"
  if (pkg.blocker_count > 0 || pkg.approval_status === "blocked") return "blockiert"
  if (pkg.recheck_required || pkg.approval_status === "stale") return "veraltet"
  if (pkg.approval_status === "approved") return "bestanden"
  return "offen"
}

export interface ExportReadiness {
  reviewStatus: ExportReviewStatus
  blockerCount: number
  fieldsReady: number
  fieldsOpen: number
}

export function summarizeExportReadiness(
  pkg: ReviewPackageDto | null
): ExportReadiness {
  const fields = pkg?.fields ?? []
  const fieldsReady = fields.filter((f) => f.status === "reviewed").length
  return {
    reviewStatus: exportReviewStatus(pkg),
    blockerCount: pkg?.blocker_count ?? 0,
    fieldsReady,
    fieldsOpen: fields.length - fieldsReady,
  }
}

// ---------------------------------------------------------------------------
// Per-field readiness for the manual Innolink copy (M10.2).
// "Kopierbereit" = technisch bereit für die MANUELLE Übernahme nach Innolink
// unter den aktuellen Beta-Prüfungen — KEINE fachliche Freigabe, KEINE
// Review-Freigabe, KEINE Einreichbereitschaft.
// ---------------------------------------------------------------------------
export type FieldReadiness =
  | "kopierbereit"
  | "platzhalter_offen"
  | "ueberarbeiten"
  | "beleg_fehlt"

export const FIELD_READINESS_LABELS: Record<FieldReadiness, string> = {
  kopierbereit: "Kopierbereit",
  platzhalter_offen: "Platzhalter offen",
  ueberarbeiten: "Überarbeiten (Prüfung veraltet)",
  beleg_fehlt: "Beleg fehlt",
}

export const FIELD_READINESS_STYLE: Record<FieldReadiness, string> = {
  kopierbereit: "bg-status-fulfilled/12 text-status-fulfilled",
  platzhalter_offen: "bg-status-partial/12 text-status-partial",
  ueberarbeiten: "bg-status-partial/12 text-status-partial",
  beleg_fehlt: "bg-destructive/10 text-destructive",
}

export const KOPIERBEREIT_LEGEND =
  "Kopierbereit = technisch bereit für die manuelle Übernahme nach Innolink " +
  "unter den aktuellen Beta-Prüfungen — keine fachliche Freigabe, keine " +
  "Review-Freigabe und keine Einreichbereitschaft."

export const NOT_FOR_SUBMISSION = "Nicht zur Einreichung"

export interface FieldReadinessRow {
  fieldId: string
  fieldName: string
  status: FieldReadiness
}

const EVIDENCE_FINDING_RE = /beleg|evidenz|fundstelle|quelle/i

/** Per-field readiness rows, precedence: Platzhalter → Beleg fehlt →
 *  Überarbeiten (stale/blocker) → Kopierbereit. */
export function fieldReadinessRows(
  fields: PortalFieldDraftDto[],
  pkg: ReviewPackageDto | null
): FieldReadinessRow[] {
  return fields.map((field) => {
    const text = field.current_version.text
    const openBlockers = (pkg?.findings ?? []).filter(
      (f) =>
        f.field_id === field.field_id &&
        f.severity === "blocker" &&
        f.status === "open"
    )
    let status: FieldReadiness = "kopierbereit"
    if (hasPlaceholder(text) || field.open_issue_count > 0) {
      status = "platzhalter_offen"
    } else if (openBlockers.some((f) => EVIDENCE_FINDING_RE.test(f.description))) {
      status = "beleg_fehlt"
    } else if (
      openBlockers.length > 0 ||
      pkg?.recheck_required ||
      pkg?.approval_status === "stale"
    ) {
      status = "ueberarbeiten"
    }
    return { fieldId: field.field_id, fieldName: field.field_name, status }
  })
}
