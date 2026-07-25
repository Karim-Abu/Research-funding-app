// Feature-Flags der Repair-Roadmap (dokumentiert je Milestone).
//
// innolinkImport (R3.3): Startoption «Bestehenden Innolink-Antrag hochladen»
// im Intake + Import-Review unter /import. Default AN; Abschalten über
// NEXT_PUBLIC_INNOLINK_IMPORT=off. Flag aus ⇒ Intake verhält sich wie vor R3
// (Start mit Projektidee), bereits erzeugte Kandidaten bleiben über die API
// erreichbar.
//
export const flags = {
  innolinkImport: process.env.NEXT_PUBLIC_INNOLINK_IMPORT !== "off",
} as const
