// Contract DataClassification (5 dimensions) + the UI-level confidentiality
// mapping. The UI exposes only three choices; finer policy is derived here and
// enforced again by the backend.

import type { DataClass } from "./types"

export type Sensitivity = "public" | "internal" | "confidential"
export type Origin =
  | "public_source"
  | "synthetic"
  | "anonymized"
  | "real_project"
export type ProcessingMode =
  | "deterministic_only"
  | "cloud_assisted"
  | "local_only"
export type WebResearchMode = "off" | "validated_public"

export interface DataClassification {
  sensitivity: Sensitivity
  origin: Origin
  processing_mode: ProcessingMode
  web_research_mode: WebResearchMode
  nda_applies: boolean
}

const FLAT_TO_CLASSIFICATION: Record<DataClass, DataClassification> = {
  public: {
    sensitivity: "public",
    origin: "synthetic",
    processing_mode: "cloud_assisted",
    web_research_mode: "validated_public",
    nda_applies: false,
  },
  internal: {
    sensitivity: "internal",
    origin: "real_project",
    processing_mode: "deterministic_only",
    web_research_mode: "off",
    nda_applies: false,
  },
  confidential: {
    sensitivity: "confidential",
    origin: "real_project",
    processing_mode: "local_only",
    web_research_mode: "off",
    nda_applies: false,
  },
  // R4.1 (Owner-Tabelle docs/repair/data-class-mapping.md §2): NDA/gesperrt →
  // deterministic_only — kein KI-Pfad irgendeiner Art für NDA-Material.
  nda: {
    sensitivity: "confidential",
    origin: "real_project",
    processing_mode: "deterministic_only",
    web_research_mode: "off",
    nda_applies: true,
  },
}

export function dataClassificationFromFlat(
  flat: DataClass
): DataClassification {
  return { ...FLAT_TO_CLASSIFICATION[flat] }
}

/** Inverse mapping for display/gating. R4.1: NDA ist jetzt als flacher Wert
 *  ausdrückbar — kein Kollaps mehr auf "confidential" (kein Marker-Verlust). */
export function flatFromDataClassification(
  classification: DataClassification
): DataClass {
  if (classification.nda_applies) return "nda"
  return classification.sensitivity
}
