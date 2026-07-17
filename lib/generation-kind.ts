export type GenerationKind =
  | "rule_template"
  | "fake_demo"
  | "model_generated"

export const GENERATION_KIND_LABELS: Record<GenerationKind, string> = {
  rule_template: "Strukturvorlage",
  fake_demo: "Demo-Vorschlag (kein echtes KI-Modell)",
  model_generated: "Live-KI-Vorschlag",
}

// Herkunfts-Töne: Live-KI (primary), Demo (amber, wie der Demo-Banner) und
// Strukturvorlage (muted) sind nie nur textlich unterscheidbar.
export const GENERATION_KIND_BADGE_CLASS: Record<GenerationKind, string> = {
  rule_template: "border-border bg-muted/50 text-muted-foreground",
  fake_demo: "border-amber-300 bg-amber-50 text-amber-900",
  model_generated: "border-primary/30 bg-primary/10 text-primary",
}

export function generationLabel(kind?: GenerationKind | null): string {
  return kind ? GENERATION_KIND_LABELS[kind] : "Herkunft nicht verifiziert"
}

export function generationActionLabel(kind?: GenerationKind | null): string {
  if (kind === "fake_demo") return "Demo-Vorschlag erstellen"
  if (kind === "model_generated") return "Text mit KI verbessern"
  return "Vorschlag erstellen"
}

