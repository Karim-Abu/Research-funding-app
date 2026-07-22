// RUN 4A — Gruppierung der Quellenliste nach Zweck. Die Zuordnung erfolgt
// ausschliesslich anhand kanonischer Metadaten (primary_application_source_id
// des Projekts und data_classification.origin der Quelle) — nie anhand von
// Dateinamen oder anderen UI-Heuristiken.

import type { SourceDocumentDto } from "./sources"

export type SourceGroupKey =
  | "primary_application"
  | "project_documents"
  | "public_research"

export const SOURCE_GROUP_ORDER: SourceGroupKey[] = [
  "primary_application",
  "project_documents",
  "public_research",
]

export const SOURCE_GROUP_LABELS: Record<SourceGroupKey, string> = {
  primary_application: "Primärer Innolink-Antrag",
  project_documents: "Projektunterlagen",
  public_research: "Öffentliche Recherche",
}

/** Zweck der Gruppe in Nutzersprache («Verwendet für/als …»). */
export const SOURCE_GROUP_DESCRIPTIONS: Record<SourceGroupKey, string> = {
  primary_application: "Verwendet für Import und Antragsanalyse.",
  project_documents: "Verwendet als Entwurfskontext.",
  public_research: "Verwendet für Markt- und Konkurrenzvergleich.",
}

/** Freundlicher Hinweis, wenn kein primärer Antrag festgelegt ist. */
export const PRIMARY_APPLICATION_HINTS: Record<
  "not_configured" | "needs_selection",
  string
> = {
  not_configured:
    "Noch kein primärer Innolink-Antrag festgelegt. Laden Sie Ihren Antrag unter «Antrag importieren» hoch — er wird dann hier geführt.",
  needs_selection:
    "Mehrere mögliche Antragsquellen gefunden. Bitte legen Sie fest, welche Quelle der primäre Innolink-Antrag ist.",
}

export function sourceGroupOf(
  doc: Pick<SourceDocumentDto, "source_id" | "data_classification">,
  primaryApplicationSourceId: string | null | undefined
): SourceGroupKey {
  if (
    primaryApplicationSourceId &&
    doc.source_id === primaryApplicationSourceId
  ) {
    return "primary_application"
  }
  if (doc.data_classification?.origin === "public_source") {
    return "public_research"
  }
  return "project_documents"
}
