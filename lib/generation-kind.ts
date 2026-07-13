export type GenerationKind =
  | "rule_template"
  | "fake_demo"
  | "model_generated"

export const GENERATION_KIND_LABELS: Record<GenerationKind, string> = {
  rule_template: "Strukturvorlage",
  fake_demo: "Demo-Vorschlag (kein echtes KI-Modell)",
  model_generated: "KI-Vorschlag",
}

export function generationLabel(kind?: GenerationKind | null): string {
  return kind ? GENERATION_KIND_LABELS[kind] : "Herkunft nicht verifiziert"
}

export function generationActionLabel(kind?: GenerationKind | null): string {
  if (kind === "fake_demo") return "Demo-Vorschlag erstellen"
  if (kind === "model_generated") return "KI-Vorschlag erstellen"
  return "Vorschlag erstellen"
}

