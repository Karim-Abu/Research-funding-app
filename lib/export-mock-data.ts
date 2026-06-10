// Dummy-Daten für den Export-Screen. Keine echten Daten, keine Backend-Aufrufe.

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
    subtitle: "Für die Weiterarbeit und den Übertrag ins Portal",
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
    isDraft: false,
  },
  {
    id: "pe3",
    filename: "KI-Materialentwicklung_Nachweis.json",
    kind: "json_audit",
    timestamp: "gestern, 17:43",
    isDraft: false,
  },
]

export const KIND_LABEL: Record<ExportKind, string> = {
  word: "Word",
  markdown: "Markdown",
  json_audit: "Technischer Nachweis",
}
