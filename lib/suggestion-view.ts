// Konkrete Begründungs-Chips für den Vorschlagsvergleich (C5) — abgeleitet
// aus dem strukturierten section_result (modell-deklarierte Listen), statt
// eines pauschalen Freitexts. Pures View-Modell: keine API, keine UI-Strings
// aus dem Backend verändert.

import type { A2Suggestion } from "@/lib/redraft"

export interface RationaleChip {
  tone: "entfernt" | "neu" | "offen"
  text: string
}

export function rationaleChips(suggestion: A2Suggestion): RationaleChip[] {
  const section = suggestion.section_result
  if (!section) return []
  const chips: RationaleChip[] = []
  // Fallbacks: Feld-Level-Vorschläge (PortalFieldDraftBundle) tragen nicht
  // alle Section-Listen — fehlende Listen bedeuten «keine Chips», nie ein
  // Renderfehler (Crash im Lauf-Vorschlag, RUN 2A Slice 0).
  for (const claim of section.removed_or_reframed_claims ?? []) {
    chips.push({ tone: "entfernt", text: `Entfernt/Umformuliert: ${claim}` })
  }
  for (const claim of section.new_claims ?? []) {
    chips.push({ tone: "neu", text: `Neue Aussage (ungeprüft): ${claim}` })
  }
  for (const input of section.missing_inputs ?? []) {
    chips.push({
      tone: "offen",
      text: `Offen gelassen: ${input.label}${input.reason ? ` — ${input.reason}` : ""}`,
    })
  }
  return chips
}
