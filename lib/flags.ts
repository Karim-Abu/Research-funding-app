// Feature-Flags der Repair-Roadmap (dokumentiert je Milestone).
//
// innolinkImport (R3.3): Startoption «Bestehenden Innolink-Antrag hochladen»
// im Intake + Import-Review unter /import. Default AN; Abschalten über
// NEXT_PUBLIC_INNOLINK_IMPORT=off. Flag aus ⇒ Intake verhält sich wie vor R3
// (Start mit Projektidee), bereits erzeugte Kandidaten bleiben über die API
// erreichbar.
//
// evalViews (Demo-Golden-Path): blendet den Sidebar-Zugang «Evaluation & Technik»
// für technische Provider-/Integrated-Draft-Ansichten ein. Default AUS — bewusst
// invers zu den Opt-out-Flags oben. Einschalten über NEXT_PUBLIC_EVAL_VIEWS=on.
// /kosten ist eine reguläre projektbezogene Transparenzseite; /admin und
// /antragsentwurf bleiben unabhängig vom Flag direkt erreichbar.
export const flags = {
  innolinkImport: process.env.NEXT_PUBLIC_INNOLINK_IMPORT !== "off",
  evalViews: process.env.NEXT_PUBLIC_EVAL_VIEWS === "on",
} as const
