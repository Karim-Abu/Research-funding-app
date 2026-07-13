// View model for the Antragsentwurf screen (DEMO.1): German labels, badge
// styles, summary counts and the copy-all working-draft text. Pure mapping —
// no fetch, no business logic.

import { cleanFieldName } from "./draft-viewmodel"
import type { DraftPackageDto, FieldDraftItemDto, FieldDraftStatus } from "./integrated-draft"
import { generationLabel } from "./generation-kind"

export const FIELD_DRAFT_STATUS_LABELS: Record<FieldDraftStatus, string> = {
  generated: "Vorschlag erstellt",
  deterministic: "Automatisch übernommen",
  missing_inputs: "Angaben fehlen",
  skipped: "Übersprungen",
  unavailable: "Nicht verfügbar",
  failed: "Fehlgeschlagen",
}

export function fieldDraftStatusLabel(field: FieldDraftItemDto): string {
  if (field.status !== "generated") return FIELD_DRAFT_STATUS_LABELS[field.status]
  return `${generationLabel(field.generation_kind)} erstellt`
}

export const FIELD_DRAFT_STATUS_STYLE: Record<FieldDraftStatus, string> = {
  generated: "bg-status-fulfilled/12 text-status-fulfilled",
  deterministic: "bg-status-fulfilled/12 text-status-fulfilled",
  missing_inputs: "bg-status-partial/12 text-status-partial",
  skipped: "bg-muted text-muted-foreground",
  unavailable: "bg-muted text-muted-foreground",
  failed: "bg-destructive/10 text-destructive",
}

export const COST_STATUS_LABELS: Record<string, string> = {
  not_applicable: "Ohne Kosten (Demo)",
  unknown_price: "Preis unbekannt",
  priced: "Bepreist",
}

export function costStatusLabel(status: string | null | undefined): string {
  if (!status) return "—"
  return COST_STATUS_LABELS[status] ?? status
}

export interface DraftSummary {
  total: number
  generated: number
  deterministic: number
  missingInputs: number
  failed: number
}

export function summarizeFields(fields: FieldDraftItemDto[]): DraftSummary {
  return {
    total: fields.length,
    generated: fields.filter((f) => f.status === "generated").length,
    deterministic: fields.filter((f) => f.status === "deterministic").length,
    missingInputs: fields.filter((f) => f.status === "missing_inputs").length,
    failed: fields.filter((f) => f.status === "failed").length,
  }
}

export function fieldLabel(field: FieldDraftItemDto): string {
  return cleanFieldName(field.field_label, field.field_id)
}

/** True for the two fields that consume advisory research context (VC/SOL). */
export function researchHint(
  pkg: DraftPackageDto,
  fieldId: string
): { label: string; used: boolean } | null {
  if (fieldId === "VC.BUSINESS_TARGETS_MODEL.EDITOR") {
    return { label: "Marktkontext genutzt", used: pkg.research_summary.market.used }
  }
  if (fieldId === "SOL.INNOVATION_SOLUTION.EDITOR") {
    return { label: "Partnerkontext genutzt", used: pkg.research_summary.partner.used }
  }
  return null
}

/** Working-draft text over all fields with a draft text — for "copy all". */
export function buildWorkingDraftText(pkg: DraftPackageDto): string {
  const parts: string[] = []
  for (const field of pkg.fields) {
    if (!field.suggestion_text) continue
    parts.push(`${fieldLabel(field)}\n\n${field.suggestion_text}`)
  }
  return parts.join("\n\n---\n\n")
}
