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

// Shorter inline hint used directly on the Evidenz screens.
export const EVIDENCE_VERIFIED_HINT =
  "«Fundstelle bestätigt» bedeutet, dass der Text in der Quelle auffindbar ist — " +
  "keine inhaltliche Freigabe. Die fachliche Bewertung erfolgt im Review."

// ---------------------------------------------------------------------------
// User-friendly fallbacks (Mock + Live). Never show raw backend values.
// ---------------------------------------------------------------------------
export const REQUIREMENT_FALLBACK = "Keine zugeordnete Anforderung"
export const FUNDSTELLE_FALLBACK = "Fundstelle nicht genau bestimmt"
export const REVIEWER_FALLBACK = "Noch nicht menschlich geprüft"

// ---------------------------------------------------------------------------
// Unified evidence filter (works for both VerificationStatus and MachineStatus)
// ---------------------------------------------------------------------------
export type EvidenceFilter =
  | "all"
  | "verified"
  | "review"
  | "open"
  | "error"
  | "no_location"

export const EVIDENCE_FILTER_LABELS: Record<EvidenceFilter, string> = {
  all: "Alle",
  verified: "Verifiziert",
  review: "Prüfung nötig",
  open: "Offen",
  error: "Fehler",
  no_location: "Ohne genaue Fundstelle",
}

export type EvidenceStatusFilter = Exclude<EvidenceFilter, "all" | "no_location">

/** Map a live VerificationStatus onto the shared filter status. */
export function verificationToFilter(s: VerificationStatus): EvidenceStatusFilter {
  switch (s) {
    case "exact_verified":
    case "human_verified":
      return "verified"
    case "unverified":
      return "review"
    case "rejected":
      return "error"
  }
}

// ---------------------------------------------------------------------------
// Fundstelle (human-readable location). Raw offsets are never shown.
// ---------------------------------------------------------------------------
interface LocationFields {
  page?: number | null
  section?: string | null
}

/** True when the anchor carries any precise location signal. */
export function hasPreciseLocation(loc: LocationFields): boolean {
  return loc.page != null || Boolean(loc.section?.trim())
}

/** Build a readable location like "S. 8 · Abschnitt 2.1" from available fields. */
export function formatFundstelle(loc: LocationFields): string {
  const parts: string[] = []
  if (loc.page != null) parts.push(`S. ${loc.page}`)
  const section = loc.section?.trim()
  if (section) {
    parts.push(/^abschnitt|^tabelle|^abb\.?|^kapitel/i.test(section) ? section : `Abschnitt ${section}`)
  }
  return parts.length > 0 ? parts.join(" · ") : FUNDSTELLE_FALLBACK
}

// ---------------------------------------------------------------------------
// Reviewer line. Internal user-/actor-ids are never shown.
// ---------------------------------------------------------------------------
function looksLikeId(value: string): boolean {
  return (
    /[0-9a-f]{8}-[0-9a-f]{4}/i.test(value) || /^(user|usr|actor|system)[-_:]/i.test(value)
  )
}

function formatWhen(at: string): string {
  const d = new Date(at)
  return Number.isNaN(d.getTime()) ? at : d.toLocaleString("de-CH")
}

/**
 * Human reviewer label, or null when nobody has checked it yet (caller shows
 * REVIEWER_FALLBACK). Falls back to a neutral phrase if the actor is an id.
 */
export function formatReviewer(
  name?: string | null,
  at?: string | null
): string | null {
  const trimmed = name?.trim()
  if (!trimmed) return null
  const when = at ? ` · ${formatWhen(at)}` : ""
  if (looksLikeId(trimmed)) return `Menschlich geprüft${when}`
  return `Geprüft von ${trimmed}${when}`
}

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
