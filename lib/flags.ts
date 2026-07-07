// Feature-Flags der Repair-Roadmap (dokumentiert je Milestone).
//
// groupedFindings (R2.5): gruppierte Findings + Fix Queue («Nächste Aufgaben»)
// auf Qualitätsprüfung/Anforderungen. Default AN; Abschalten für Demo/Debug
// über NEXT_PUBLIC_GROUPED_FINDINGS=off (Build-Zeit-Variable). Bei fehlenden
// grouped_findings fällt die UI unabhängig vom Flag auf die alte Liste zurück.
export const flags = {
  groupedFindings: process.env.NEXT_PUBLIC_GROUPED_FINDINGS !== "off",
} as const
