// Dummy-Daten für den Export-Screen. Keine echten Daten, keine Backend-Aufrufe.

import { draftFields } from "./draft-mock-data"
import type { DraftStatus, PortalFieldDraftDto } from "./fields"

export type ApprovalBannerState = "approved" | "not_approved" | "stale"

export type ExportCardStatus = "ready" | "generating" | "error"

export type ExportKind = "word" | "markdown" | "json_audit"

export interface ExportCard {
  id: string
  kind: ExportKind
  title: string
  subtitle: string
  status: ExportCardStatus
  /** When true, this card is the visually leading one (primary button). */
  leading: boolean
}

export interface PriorExport {
  id: string
  filename: string
  kind: ExportKind
  timestamp: string
  /** When true, the file was exported without a valid approval (draft stamp). */
  isDraft: boolean
}

export type PageScenario =
  | "default"
  | "approved"
  | "stale"
  | "nothing_to_export"
  | "generating"
  | "error"

export const PAGE_SCENARIOS: { id: PageScenario; label: string }[] = [
  { id: "default", label: "Standard (nicht freigegeben)" },
  { id: "approved", label: "Freigegeben" },
  { id: "stale", label: "Freigabe veraltet" },
  { id: "nothing_to_export", label: "Nichts zu exportieren" },
  { id: "generating", label: "Wird erstellt…" },
  { id: "error", label: "Fehler" },
]

export const EXPORT_CARDS: ExportCard[] = [
  {
    id: "word",
    kind: "word",
    title: "Word-Arbeitsdokument",
    subtitle: "Editierbares Arbeitsdokument zur Weiterbearbeitung im Antragsteam.",
    status: "ready",
    leading: true,
  },
  {
    id: "markdown",
    kind: "markdown",
    title: "Markdown-Zusammenfassung",
    subtitle: "Kompakte Textfassung",
    status: "ready",
    leading: false,
  },
  {
    id: "json_audit",
    kind: "json_audit",
    title: "Technischer Nachweis",
    subtitle: "JSON für Audit und Weiterverarbeitung",
    status: "ready",
    leading: false,
  },
]

// 3 prior exports, one with _ENTWURF filename suffix.
export const PRIOR_EXPORTS: PriorExport[] = [
  {
    id: "pe1",
    filename: "KI-Materialentwicklung_Antrag_ENTWURF.docx",
    kind: "word",
    timestamp: "heute, 08:14",
    isDraft: true,
  },
  {
    id: "pe2",
    filename: "KI-Materialentwicklung_Zusammenfassung.md",
    kind: "markdown",
    timestamp: "gestern, 17:42",
    isDraft: true,
  },
  {
    id: "pe3",
    filename: "KI-Materialentwicklung_Nachweis.json",
    kind: "json_audit",
    timestamp: "gestern, 17:43",
    isDraft: true,
  },
]

export const KIND_LABEL: Record<ExportKind, string> = {
  word: "Word",
  markdown: "Markdown",
  json_audit: "Technischer Nachweis",
}

// ---------------------------------------------------------------------------
// Innolink copy view (mock): reuse the editor's portal fields, mapped onto the
// PortalFieldDraftDto shape the FieldTransferCard expects. No backend.
// ---------------------------------------------------------------------------
const DRAFT_STATUS_TO_PORTAL: Record<string, DraftStatus> = {
  ready: "reviewed",
  needs_review: "needs_review",
  no_evidence: "needs_review",
  blocked: "blocked",
  open: "draft",
}

export const mockInnolinkFields: PortalFieldDraftDto[] = draftFields.map((f) => {
  const text = f.text
  const count = [...text].length
  return {
    draft_id: f.id,
    field_id: f.id,
    field_name: f.name,
    status: DRAFT_STATUS_TO_PORTAL[f.status] ?? "draft",
    current_version: {
      draft_version_id: `${f.id}-v1`,
      text,
      character_count: count,
      created_by: "user",
      created_at: "2026-06-25T09:42:00.000Z",
      content_hash: "mock",
    },
    character_count: count,
    character_limit: f.charLimit ?? null,
    open_issue_count: f.openPoints.length,
    evidence_links: [],
    open_issues: [],
  }
})
