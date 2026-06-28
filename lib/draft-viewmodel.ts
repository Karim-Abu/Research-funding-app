// UI-only ViewModel for the Entwurf workspace. Maps mock and live data onto one
// shape so both modes render the same shell. NO data mutation, NO persistence,
// NO review business logic — purely presentational mapping + fallbacks.

import type { DraftFieldStatus, DraftEvidenceStatus } from "./draft-view"
import type { MarketStatus } from "./market-view"
import type { ReqBucket } from "./requirements-view"
import type { PortalFieldDraftDto } from "./fields"
import type { ReviewPackageDto } from "./review"

export interface VMPerson {
  name: string
  initials: string
}

export interface VMEvidence {
  id: string
  claim: string
  source: string
  fundstelle: string
  status: DraftEvidenceStatus
}

export interface VMRequirement {
  id: string
  title: string
  status: ReqBucket
}

export interface VMComment {
  id: string
  author: VMPerson
  timestamp: string
  text: string
  resolved: boolean
}

export interface VMVersion {
  id: string
  label: string
  timestamp: string
  author: string
  current?: boolean
}

export interface DraftFieldViewModel {
  id: string
  sectionLabel: string
  fieldLabel: string
  /** Small German helper label under the field name. */
  helperLabel?: string
  /** Original/technical label — only shown under "Technische Details". */
  originalFieldLabel?: string
  status: DraftFieldStatus
  characterLimit?: number | null
  /** Server/initial text (the editor manages its own editable buffer). */
  text: string
  lastEditedLabel?: string
  evidenceCount: number
  openIssueCount: number
  commentCount: number
  hasPlaceholder: boolean
  isMarketRelevant: boolean
  marketStatus?: MarketStatus
  evidenceItems: VMEvidence[]
  requirementItems: VMRequirement[]
  responsible?: VMPerson
  reviewer?: VMPerson
  versions: VMVersion[]
  technicalDetails: { label: string; value: string }[]
}

// ---------------------------------------------------------------------------
// Field name + section helpers — never expose raw technical labels.
// ---------------------------------------------------------------------------
const SECTION_LABELS: Record<string, string> = {
  INTRO: "Introduction",
  ORG: "Organisations & People",
  VC: "Value Creation",
  SOL: "Solution",
  PS: "Project Setup",
  SUMMARY: "Summary & Submit",
}

export function sectionLabelFromFieldId(fieldId: string): string {
  return SECTION_LABELS[fieldId.split(".")[0]] ?? "Weitere Felder"
}

export function isMarketRelevantFieldId(fieldId: string): boolean {
  const prefix = fieldId.split(".")[0]
  return prefix === "VC" || prefix === "SOL"
}

// Known technical Innolink labels → user-friendly portal field names.
const KNOWN_FIELD_LABELS: Record<string, string> = {
  "value creation editor": "Business Targets & Business Model",
  "solution editor": "Innovation Solution",
  "project setup explanation": "Project Plan / Management Hours",
}

/** Strip technical wrappers like "Open Editor (Editor for X)" → "X". */
export function cleanFieldName(name: string | null | undefined, fieldId: string): string {
  const raw = (name ?? "").trim()
  const known = KNOWN_FIELD_LABELS[raw.toLowerCase()]
  if (known) return known
  const match = /(?:open editor\s*\()?\s*editor for\s+(.+?)\)?\s*$/i.exec(raw)
  if (match) return match[1].trim()
  if (raw && !/^open editor/i.test(raw)) return raw
  const segment = fieldId.split(".").pop() ?? fieldId
  const humanized = segment
    .replace(/[_-]+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
  return humanized || "Unbenanntes Feld"
}

// Small German helper label shown under the (English) Innolink field name.
const HELPER_LABELS: Record<string, string> = {
  "Business Targets & Business Model": "Geschäftsziele & Geschäftsmodell",
  "Innovation Solution": "Lösung & Innovation",
  "Project Plan": "Projektplan",
  "Project Plan / Management Hours": "Projektplan",
}

export function helperLabel(fieldLabel: string): string | undefined {
  return HELPER_LABELS[fieldLabel]
}

// ---------------------------------------------------------------------------
// Live adapter — maps the contract DTO. Missing data → clean fallbacks.
// ---------------------------------------------------------------------------
export function liveFieldToViewModel(
  dto: PortalFieldDraftDto,
  _review: ReviewPackageDto | null
): DraftFieldViewModel {
  const cleanedName = cleanFieldName(dto.field_name, dto.field_id)
  const original =
    dto.field_name && dto.field_name.trim() !== cleanedName ? dto.field_name.trim() : undefined
  const activeLinks = dto.evidence_links.filter((l) => l.status === "active").length
  const technicalDetails: { label: string; value: string }[] = [
    { label: "Feld-ID", value: dto.field_id },
  ]
  if (original) technicalDetails.push({ label: "Original-Bezeichnung", value: original })

  return {
    id: dto.field_id,
    sectionLabel: sectionLabelFromFieldId(dto.field_id),
    fieldLabel: cleanedName,
    helperLabel: helperLabel(cleanedName),
    originalFieldLabel: original,
    status: liveStatusToDraftStatus(dto.status, dto.open_issue_count),
    characterLimit: dto.character_limit ?? null,
    text: dto.current_version.text,
    lastEditedLabel: dto.current_version.created_at
      ? `Zuletzt geändert: ${new Date(dto.current_version.created_at).toLocaleString("de-CH")}`
      : undefined,
    evidenceCount: activeLinks,
    openIssueCount: dto.open_issue_count,
    commentCount: 0,
    hasPlaceholder: false, // computed live from the editable buffer in the editor
    isMarketRelevant: isMarketRelevantFieldId(dto.field_id),
    marketStatus: undefined, // live has no market analysis yet → empty state
    evidenceItems: [],
    requirementItems: [],
    responsible: undefined,
    reviewer: undefined,
    versions: [],
    technicalDetails,
  }
}

function liveStatusToDraftStatus(
  status: PortalFieldDraftDto["status"],
  openIssueCount: number
): DraftFieldStatus {
  switch (status) {
    case "reviewed":
      return "ready"
    case "needs_review":
      return "needs_review"
    case "blocked":
      return "blocked"
    case "stale":
      return "needs_review"
    case "draft":
      return openIssueCount > 0 ? "open" : "needs_review"
  }
}

// ---------------------------------------------------------------------------
// Default assistant tab — priority order (see plan). Pure UI decision.
// ---------------------------------------------------------------------------
export type AssistantTab =
  | "markt"
  | "belege"
  | "anforderungen"
  | "kommentare"
  | "versionen"

export function pickDefaultTab(
  vm: DraftFieldViewModel,
  opts: { hasMarketData: boolean; hasFindings: boolean; hasBlocker: boolean }
): AssistantTab {
  if (opts.hasMarketData && vm.isMarketRelevant) return "markt"
  if (opts.hasFindings || vm.commentCount > 0 || opts.hasBlocker) return "kommentare"
  if (vm.evidenceCount > 0) return "belege"
  if (vm.isMarketRelevant) return "markt"
  return "anforderungen"
}
