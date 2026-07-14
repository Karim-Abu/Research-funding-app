// Public web research client (M9I-A, same-origin BFF). Drives the "Öffentliche
// Recherche" panel: start a task, poll the operation, list candidates, import one as a
// normal source. No provider/Firecrawl/API terminology is ever surfaced here.

import { getCsrfToken } from "./session"
import type { SourceDocumentDto } from "./sources"

export type ResearchTaskStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"

export type ResearchPurpose =
  | "partner_role_suggestion"
  | "competence_gap_analysis"
  | "publication_track_record"

export type SubjectType = "person" | "organisation" | "topic"

export interface AsyncAcceptedDto {
  operation_id: string
  resource_type: string
  resource_id: string
  status: "queued" | "running"
  poll_url: string
}

export interface ProfessionalEvidenceDto {
  professional_evidence_id: string
  evidence_type: string
  subject_name: string
  organisation?: string | null
  claim: string
  source_url: string
  source_title: string
  accessed_at: string
  source_id?: string | null
}

export interface PartnerRoleSuggestionDto {
  suggestion_id: string
  role_name: string
  competence_gap: string
  suggested_subject_name?: string | null
  suggested_organisation?: string | null
  professional_evidence_ids: string[]
  status: "suggested" | "accepted" | "rejected"
  human_review_required: boolean
}

export interface ResearchResultDto {
  result_id: string
  task_id: string
  source_url: string
  title: string
  snippet?: string | null
  accessed_at: string
  status: "candidate" | "imported" | "rejected"
  professional_evidence: ProfessionalEvidenceDto[]
  partner_role_suggestions: PartnerRoleSuggestionDto[]
  identity_match_status: "not_applicable" | "matched" | "ambiguous" | "unresolved"
}

export interface ResearchTaskInput {
  purpose: ResearchPurpose
  subject_type: SubjectType
  subject_name?: string | null
  query_preview: string
  max_results: number
  competence_needs?: string[]
  requested_partner_roles?: string[]
  // M9J: for a confidential (D1/D2) project, the id of a firewall-sanitized, approved
  // query. The raw query never reaches the provider; only the sanitized query is sent.
  approval_id?: string
}

const STATUS_MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Diese Aktion ist nicht erlaubt oder durch die Datenrichtlinie blockiert.",
  422: "Öffentliche Recherche ist für diese Datenklasse nicht erlaubt.",
  429: "Das Limit für die Recherche ist erreicht. Bitte versuchen Sie es später erneut.",
  502: "Die Quelle konnte nicht abgerufen werden. Bitte versuchen Sie eine andere Quelle.",
  503: "Die öffentliche Recherche ist derzeit nicht verfügbar.",
}

export class ResearchError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "ResearchError"
    this.status = status
    this.code = code
  }
}

function idempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, "")
}

function csrfHeaders(): Record<string, string> {
  const csrf = getCsrfToken()
  return csrf ? { "X-CSRF-Token": csrf } : {}
}

async function toError(res: Response): Promise<ResearchError> {
  let code = "error"
  try {
    const body = await res.json()
    if (body?.code) code = body.code
  } catch {
    // non-JSON body; fall back to a generic message
  }
  return new ResearchError(
    res.status,
    code,
    STATUS_MESSAGES[res.status] ?? "Es ist ein Fehler aufgetreten."
  )
}

/** @deprecated Normal UI uses the approved public research brief workflow. */
export async function createResearchTask(
  projectId: string,
  input: ResearchTaskInput
): Promise<AsyncAcceptedDto> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/research-tasks`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      body: JSON.stringify({
        ...input,
        user_confirms_public_professional_purpose: true,
      }),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as AsyncAcceptedDto
}

export async function listResearchResults(
  projectId: string
): Promise<ResearchResultDto[]> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/research-results`
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as ResearchResultDto[]
}

export async function importResearchResult(
  resultId: string
): Promise<SourceDocumentDto> {
  const res = await fetch(
    `/api/research-results/${encodeURIComponent(resultId)}/import`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey(), ...csrfHeaders() },
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as SourceDocumentDto
}

// R8: Ergebnis-Kandidat persistent verwerfen (candidate → rejected) — verworfene
// Ergebnisse werden nie KI-Kontext und bleiben nach Reload verworfen.
export async function discardResearchResult(
  resultId: string
): Promise<ResearchResultDto> {
  const res = await fetch(
    `/api/research-results/${encodeURIComponent(resultId)}/discard`,
    {
      method: "POST",
      headers: { ...csrfHeaders() },
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as ResearchResultDto
}
