// R3.3 — Client für den Innolink-Antragsimport (same-origin BFF).
// Upload läuft über lib/sources.ts (bestehender Quellen-Pfad); hier: Mapping
// einer verarbeiteten Quelle auf Portal-Felder + HITL-Entscheidungen.

import { getCsrfToken } from "./session"

export type ImportConfidence = "found" | "uncertain"
export type ImportMappingStatus =
  | "content_detected"
  | "empty"
  | "legacy_migrated"
  | "uncertain"
export type ImportDecision =
  | "pending"
  | "conflict"
  | "accepted"
  | "saved_as_source"
  | "ignored"

export interface ImportSectionMetadataDto {
  target_sections: string[]
  source_location: string | null
  status: ImportMappingStatus
  candidate_text: string
  /** Unveränderter Quellbereich; kann vertraulichen Antragstext enthalten. */
  original_excerpt: string
  migration_version: string | null
  requires_manual_assignment: boolean
  review_note: string | null
}

export interface ImportCandidateDto {
  import_candidate_id: string
  source_id: string
  field_id: string
  /** Deutsches Anzeige-Label — die UI zeigt nie rohe Feld-IDs. */
  label: string
  extracted_text: string
  /** «Bearbeitet übernommen»: editierter Text; extracted_text bleibt das
   *  unveränderte Original (Originalausschnitt). */
  edited_text: string | null
  confidence: ImportConfidence
  source_location: string | null
  mapping_version: string
  mapping_status: ImportMappingStatus
  section_metadata: ImportSectionMetadataDto[]
  decision: ImportDecision
  decided_at: string | null
  accepted_draft_version_id: string | null
}

export type StructuredCandidateKind =
  | "project_metadata"
  | "partner"
  | "budget"
  | "answer"
export type StructuredImportDecision =
  | "pending"
  | "accepted"
  | "ignored"
  | "conflict"

export interface StructuredImportCandidateDto {
  candidate_id: string
  source_id: string
  candidate_kind: StructuredCandidateKind
  target_key: string
  label: string
  payload_json: Record<string, unknown>
  edited_payload_json: Record<string, unknown> | null
  effective_payload_json: Record<string, unknown>
  confidence: ImportConfidence
  source_location: string | null
  mapping_version: string
  decision: StructuredImportDecision
  decided_at: string | null
  applied_resource_id: string | null
  current_value_json: Record<string, unknown> | null
  has_conflict: boolean
  conflict_reason: string | null
  requires_manual_edit: boolean
  interaction_mode: "actionable" | "comparison_only"
  derived_duration_months: number | null
  duration_status: "derived" | "not_derivable" | "review_required" | null
  duration_reason_code: string | null
  duration_comparison_status:
    | "duration_match"
    | "duration_conflict"
    | "not_derivable"
    | "duration_boundary_conflict"
    | null
}

export interface StructuredImportSummaryDto {
  partners: { detected: number; reviewed: number; unchecked: number }
  budget: { detected: number; reviewed: number; unchecked: number }
  provenance: Array<{
    candidate_kind: "partner" | "budget"
    target_key: string
    applied_resource_id: string
    source_location: string | null
    state: "confirmed" | "changed_after_import" | "missing"
  }>
}

const STATUS_MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Diese Aktion ist nicht erlaubt oder durch die Datenrichtlinie blockiert.",
  409: "Die Aktion steht im Konflikt mit dem aktuellen Zustand.",
  422: "Die Eingabe ist ungültig.",
  429: "Das Limit ist erreicht. Bitte versuchen Sie es später erneut.",
  503: "Der Dienst ist derzeit nicht verfügbar.",
}

export class ImportError extends Error {
  readonly status: number
  readonly code: string
  /** Correlation-ID des Backends — nur für «Technische Details» gedacht. */
  readonly correlationId: string | null
  constructor(
    status: number,
    code: string,
    message: string,
    correlationId: string | null = null
  ) {
    super(message)
    this.name = "ImportError"
    this.status = status
    this.code = code
    this.correlationId = correlationId
  }
}

function idempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, "")
}

function csrfHeaders(): Record<string, string> {
  const csrf = getCsrfToken()
  return csrf ? { "X-CSRF-Token": csrf } : {}
}

async function toError(res: Response): Promise<ImportError> {
  let code = "error"
  let detail: string | null = null
  let correlation: string | null = null
  try {
    const body = await res.json()
    if (body?.code) code = body.code
    // Backend-Problem-Details sind bereits deutsche, nutzerlesbare Sätze.
    if (typeof body?.detail === "string" && body.detail) detail = body.detail
    if (typeof body?.correlation_id === "string") correlation = body.correlation_id
  } catch {
    // non-JSON body
  }
  return new ImportError(
    res.status,
    code,
    detail ?? STATUS_MESSAGES[res.status] ?? "Es ist ein Fehler aufgetreten.",
    correlation ?? res.headers.get("x-correlation-id")
  )
}

export async function getImportCandidates(
  projectId: string
): Promise<ImportCandidateDto[]> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/imports`
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as ImportCandidateDto[]
}

export async function getStructuredImportCandidates(
  projectId: string
): Promise<StructuredImportCandidateDto[]> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/structured-imports`
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as StructuredImportCandidateDto[]
}

export async function getStructuredImportSummary(
  projectId: string
): Promise<StructuredImportSummaryDto> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/structured-imports/summary`
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as StructuredImportSummaryDto
}

export async function createImportCandidates(
  projectId: string,
  sourceId: string
): Promise<ImportCandidateDto[]> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/imports`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      body: JSON.stringify({ source_id: sourceId }),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as ImportCandidateDto[]
}

export async function decideImportCandidate(
  candidateId: string,
  payload: {
    decision: "accepted" | "saved_as_source" | "ignored"
    /** Optional: ohne run_id wird die Übernahme projektbezogen vorgemerkt
     *  und beim nächsten Analyse-Lauf als Entwurfsbasis konsumiert. */
    run_id?: string
    /** «Bearbeitet übernommen» (nur bei accepted). */
    edited_text?: string
    confirm_overwrite?: boolean
  }
): Promise<ImportCandidateDto> {
  const res = await fetch(
    `/api/imports/${encodeURIComponent(candidateId)}/decision`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      body: JSON.stringify(payload),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as ImportCandidateDto
}

export async function decideStructuredImportCandidate(
  candidateId: string,
  payload: {
    decision: "accepted" | "ignored"
    edited_payload_json?: Record<string, unknown>
    confirm_overwrite?: boolean
  }
): Promise<StructuredImportCandidateDto> {
  const res = await fetch(
    `/api/structured-imports/${encodeURIComponent(candidateId)}/decision`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      body: JSON.stringify(payload),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as StructuredImportCandidateDto
}
