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
}

export function dataClassificationFromFlat(
  flat: DataClass
): DataClassification {
  return { ...FLAT_TO_CLASSIFICATION[flat] }
}

/** Inverse mapping for display/gating: NDA is not expressible in the flat
 *  choice, so it collapses to the most restrictive flat value. */
export function flatFromDataClassification(
  classification: DataClassification
): DataClass {
  if (classification.nda_applies) return "confidential"
  return classification.sensitivity
}
