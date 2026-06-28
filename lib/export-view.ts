// Presentation helpers for the Export screen + Innolink copy view. Pure
// functions over existing DTOs — no backend calls, no contract changes.

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
