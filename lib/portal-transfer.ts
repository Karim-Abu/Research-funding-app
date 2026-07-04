// Innolink transfer helpers (Milestone 8.1): registry-order grouping, placeholder
// detection, per-field copy warnings, and the unsupported-area coverage list.
// Pure functions over existing DTOs — no new API, no backend.

import type { PortalFieldDraftDto } from "./fields"
import type { ReviewPackageDto } from "./review"

// Canonical Innolink portal sections (field-id prefix → label). Mirrors the
// editor's section map; the field ORDER comes from listFields (registry order),
// not re-sorted here.
export const SECTION_LABELS: Record<string, string> = {
  INTRO: "Einleitung",
  ORG: "Organisation & Partner",
  VC: "Wertschöpfung",
  SOL: "Lösung & Innovation",
  PS: "Projektplan",
}
export const SECTION_ORDER = ["INTRO", "ORG", "VC", "SOL", "PS"] as const

export function sectionKey(fieldId: string): string {
  return fieldId.split(".")[0]
}

export function sectionLabel(fieldId: string): string {
  return SECTION_LABELS[sectionKey(fieldId)] ?? "Weitere"
}

// Visible, machine-detectable placeholder syntax from M6: [[Angabe ergänzen: …]].
// TODO(P2): This regex is stricter than the editor's placeholder detection in
// lib/draft-view.ts (which also matches TODO/tbd/[[…]]). Unifying them changes
// placeholder counts and field readiness — align deliberately, not silently.
const PLACEHOLDER_RE = /\[\[Angabe ergänzen:[^\]]*\]\]/g

export function countPlaceholders(text: string): number {
  return (text.match(PLACEHOLDER_RE) ?? []).length
}

export function hasPlaceholder(text: string): boolean {
  return countPlaceholders(text) > 0
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
    const approvalNotCurrent =
      review.recheck_required || review.approval_status !== "approved"
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
