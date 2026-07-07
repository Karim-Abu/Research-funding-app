// Feature-Flags der Repair-Roadmap (dokumentiert je Milestone).
//
// groupedFindings (R2.5): gruppierte Findings + Fix Queue («Nächste Aufgaben»)
// auf Qualitätsprüfung/Anforderungen. Default AN; Abschalten für Demo/Debug
// über NEXT_PUBLIC_GROUPED_FINDINGS=off (Build-Zeit-Variable). Bei fehlenden
// grouped_findings fällt die UI unabhängig vom Flag auf die alte Liste zurück.
//
// innolinkImport (R3.3): Startoption «Bestehenden Innolink-Antrag hochladen»
// im Intake + Import-Review unter /import. Default AN; Abschalten über
// NEXT_PUBLIC_INNOLINK_IMPORT=off. Flag aus ⇒ Intake verhält sich wie vor R3
// (Start mit Projektidee), bereits erzeugte Kandidaten bleiben über die API
// erreichbar.
export const flags = {
  groupedFindings: process.env.NEXT_PUBLIC_GROUPED_FINDINGS !== "off",
  innolinkImport: process.env.NEXT_PUBLIC_INNOLINK_IMPORT !== "off",
} as const
