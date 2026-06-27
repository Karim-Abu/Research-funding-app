// Evidence client (live v1.1 slice). listEvidence returns the run-scoped
// EvidenceAnchors of the deterministic baseline. Requirement context is joined
// client-side via listRequirements.evidence_links — the anchor API stays pure.

export type VerificationStatus =
  | "unverified"
  | "exact_verified"
  | "human_verified"
  | "rejected"
export type EvidenceMatchType = "exact_normalized" | "fuzzy" | "semantic" | "manual"
export type EvidenceSourceType = "pdf" | "docx" | "txt" | "url"
export type EvidenceLinkStatus = "active" | "stale" | "removed"

export interface EvidenceAnchorDto {
  anchor_id: string
  source_version_id: string
  fragment_id: string
  quote: string
  verification_status: VerificationStatus
  source_id: string
  source_name: string
  source_type: EvidenceSourceType
  normalizer_version: string
  page?: number | null
  section?: string | null
  match_type?: EvidenceMatchType | null
  human_checked_by?: string | null
  human_checked_at?: string | null
  start_offset?: number | null
  end_offset?: number | null
  match_score?: number | null
  coverage?: number | null
  source_accessed_at?: string | null
}

export interface EvidenceLinkDto {
  evidence_link_id: string
  anchor_id: string
  target_type:
    | "requirement_assessment"
    | "draft_version"
    | "draft_claim"
    | "review_finding"
    | "extracted_fact"
  target_id: string
  status: EvidenceLinkStatus
  created_at: string
  claim_id?: string | null
  claim_text?: string | null
}

// User-facing labels. human_verified is mapped but NEVER shown in M5 (no
// HumanDecision exists yet).
export const VERIFICATION_LABELS: Record<VerificationStatus, string> = {
  exact_verified: "Fundstelle bestätigt",
  unverified: "Prüfen",
  rejected: "Nicht bestätigt",
  human_verified: "Menschlich geprüft",
}

// User-facing labels for the link lifecycle between a draft/claim and its
// evidence anchor. Keeps raw enum values ("active"/"stale"/"removed") out of UI.
export const EVIDENCE_LINK_STATUS_LABELS: Record<EvidenceLinkStatus, string> = {
  active: "Aktiv",
  stale: "Veraltet",
  removed: "Entfernt",
}

// "Fundstelle bestätigt" = the quote exists verbatim in the source. It does NOT
// mean the statement has been fachlich (substantively) approved.
export const VERIFIED_EXPLANATION =
  "«Fundstelle bestätigt» bedeutet, dass das Zitat exakt in der Quelle vorkommt. Es bedeutet nicht, dass die Aussage fachlich geprüft oder genehmigt wurde."

export async function listEvidence(
  runId: string
): Promise<EvidenceAnchorDto[]> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/evidence`)
  if (!res.ok) {
    throw new Error(
      res.status === 404
        ? "Die Prüfung wurde nicht gefunden."
        : "Die Belege konnten nicht geladen werden."
    )
  }
  return (await res.json()) as EvidenceAnchorDto[]
}
