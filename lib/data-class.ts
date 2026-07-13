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

// The flat UI confidentiality choice mapped to a privacy class. R4.1: "nda" maps
// to D3; only an explicit "public" maps to D0 — anything else is UNKNOWN
// (fail-closed). The backend re-derives and enforces this regardless.
export function flatToPrivacyClass(flat: DataClass): PrivacyDataClass {
  if (flat === "nda") return "D3_NDA_BLOCKED"
  if (flat === "confidential") return "D2_CONFIDENTIAL_IDEA"
  if (flat === "internal") return "D1_INTERNAL"
  if (flat === "public") return "D0_PUBLIC"
  return "UNKNOWN"
}

// D3/UNKNOWN never reach any external research surface — not even sanitized.
export function isExternalBlocked(dc: PrivacyDataClass): boolean {
  return dc === "D3_NDA_BLOCKED" || dc === "UNKNOWN"
}

// D1/D2 must obtain a firewall-sanitized, human-approved query before web research.
export function requiresSanitizedApproval(dc: PrivacyDataClass): boolean {
  return dc === "D1_INTERNAL" || dc === "D2_CONFIDENTIAL_IDEA"
}
