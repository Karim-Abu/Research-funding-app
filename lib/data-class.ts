// Privacy data classes D0–D3/UNKNOWN (Milestone 9J) — the UI mirror of the backend
// derivation. Used only to decide whether the public-research panel must route a query
// through the Search Query Firewall (sanitize + approve) before searching. The backend
// re-derives and re-enforces this; the UI never relaxes it.

import type { DataClass } from "./types"
import type { DataClassification } from "./data-classification"

export type PrivacyDataClass =
  | "D0_PUBLIC"
  | "D1_INTERNAL"
  | "D2_CONFIDENTIAL_IDEA"
  | "D3_NDA_BLOCKED"
  | "UNKNOWN"

const PUBLIC_ORIGINS = new Set(["public_source", "synthetic"])

export function deriveDataClass(
  classification: DataClassification | null | undefined
): PrivacyDataClass {
  const cls = classification
  if (!cls || !cls.sensitivity) return "UNKNOWN"
  if (cls.nda_applies) return "D3_NDA_BLOCKED"
  if (cls.sensitivity === "confidential") return "D2_CONFIDENTIAL_IDEA"
  if (cls.sensitivity === "internal") return "D1_INTERNAL"
  if (cls.sensitivity === "public") {
    return PUBLIC_ORIGINS.has(cls.origin) ? "D0_PUBLIC" : "UNKNOWN"
  }
  return "UNKNOWN"
}

// The flat UI confidentiality choice (public/internal/confidential) mapped to a privacy
// class. NDA is not expressible in the flat choice; the backend still enforces D3.
export function flatToPrivacyClass(flat: DataClass): PrivacyDataClass {
  if (flat === "confidential") return "D2_CONFIDENTIAL_IDEA"
  if (flat === "internal") return "D1_INTERNAL"
  return "D0_PUBLIC"
}

// D1/D2 must obtain a firewall-sanitized, human-approved query before web research.
export function requiresSanitizedApproval(dc: PrivacyDataClass): boolean {
  return dc === "D1_INTERNAL" || dc === "D2_CONFIDENTIAL_IDEA"
}
