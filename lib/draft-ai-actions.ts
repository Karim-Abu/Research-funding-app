// Shared deterministic template actions for the Entwurf workspace. Kept in a plain
// module (no React) so the shell, mock and live editor can import it without
// circular component imports.

export interface AiGoal {
  key: string
  label: string
}

/** Primary entry point — creates a first suggestion (defaults to "verbessern"). */
export const AI_PRIMARY = { key: "create", label: "Strukturvorlage erstellen" }

/** Compact "Ziel des Vorschlags" chips shown inside the template panel. */
export const AI_GOALS: AiGoal[] = [
  { key: "create", label: "Verbessern" },
  { key: "shorten", label: "Kürzen" },
  { key: "innovation", label: "Innovation" },
  { key: "practice", label: "Praxisnutzen" },
  { key: "market", label: "Marktargument" },
  { key: "competition", label: "Konkurrenzabgrenzung" },
  { key: "science", label: "Wissenschaftliche Fundierung" },
]
