// Contract DataClassification (5 dimensions) + the frozen mapping from the
// legacy flat intake DataClass. The mapping is covered by a unit test so it
// cannot drift silently (audit finding FE-P0-06, milestone-scoped).

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

// Frozen old→new mapping (see Frontend_Implementation_Plan_v1 / milestone plan).
const FLAT_TO_CLASSIFICATION: Record<DataClass, DataClassification> = {
  public_synthetic: {
    sensitivity: "public",
    origin: "synthetic",
    processing_mode: "cloud_assisted",
    web_research_mode: "off",
    nda_applies: false,
  },
  public_external: {
    sensitivity: "public",
    origin: "public_source",
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
  nda: {
    sensitivity: "confidential",
    origin: "real_project",
    processing_mode: "local_only",
    web_research_mode: "off",
    nda_applies: true,
  },
}

export function dataClassificationFromFlat(
  flat: DataClass
): DataClassification {
  return { ...FLAT_TO_CLASSIFICATION[flat] }
}
