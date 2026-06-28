// Fields client (live v1.1 slice). Deterministic template drafts with immutable
// versions + base_version_id optimistic concurrency. Mirrors the openapi
// PortalFieldDraft / DraftVersion / DraftPatch / EvidenceLinkCreate shapes.

import { getCsrfToken } from "./session"
import type { EvidenceLinkDto } from "./evidence"
import type { OpenIssueDto } from "./requirements"

export type DraftStatus = "draft" | "needs_review" | "reviewed" | "blocked" | "stale"
export type CreatedBy = "agent" | "user" | "template"

export interface DraftVersionDto {
  draft_version_id: string
  text: string
  character_count: number
  created_by: CreatedBy
  created_at: string
  content_hash: string
}

export interface PortalFieldDraftDto {
  draft_id: string
  field_id: string
  field_name: string
  status: DraftStatus
  current_version: DraftVersionDto
  character_count: number
  character_limit?: number | null
  open_issue_count: number
  evidence_links: EvidenceLinkDto[]
  open_issues: OpenIssueDto[]
}

// Canonical character count — Unicode code points; matches backend len(str).
export function charCount(text: string): number {
  return [...text].length
}

export class FieldError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "FieldError"
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

const MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Diese Aktion ist nicht erlaubt.",
  404: "Der Abschnitt wurde nicht gefunden.",
  409: "Dieser Abschnitt wurde zwischenzeitlich geändert.",
  422: "Der Text überschreitet das erlaubte Zeichenlimit.",
}

async function toError(res: Response): Promise<FieldError> {
  let code = "error"
  try {
    const body = await res.json()
    if (body?.code) code = body.code
  } catch {
    /* non-JSON */
  }
  return new FieldError(res.status, code, MESSAGES[res.status] ?? "Es ist ein Fehler aufgetreten.")
}

export async function listFields(runId: string): Promise<PortalFieldDraftDto[]> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/fields`)
  if (!res.ok) throw await toError(res)
  return (await res.json()) as PortalFieldDraftDto[]
}

export async function getField(
  runId: string,
  fieldId: string
): Promise<PortalFieldDraftDto> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/fields/${encodeURIComponent(fieldId)}`
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as PortalFieldDraftDto
}

export async function updateField(
  runId: string,
  fieldId: string,
  baseVersionId: string,
  text: string,
  // Milestone 9D: set when accepting an A2 suggestion → the backend records the
  // new version as created_by=agent and marks the suggestion accepted.
  sourceOperationId?: string
): Promise<PortalFieldDraftDto> {
  const body: Record<string, unknown> = { base_version_id: baseVersionId, text }
  if (sourceOperationId) body.source_operation_id = sourceOperationId
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/fields/${encodeURIComponent(fieldId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify(body),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as PortalFieldDraftDto
}

export async function createEvidenceLink(
  runId: string,
  fieldId: string,
  anchorId: string,
  baseVersionId: string
): Promise<EvidenceLinkDto> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/fields/${encodeURIComponent(fieldId)}/evidence-links`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      body: JSON.stringify({ anchor_id: anchorId, base_version_id: baseVersionId }),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as EvidenceLinkDto
}

export async function deleteEvidenceLink(
  runId: string,
  fieldId: string,
  evidenceLinkId: string
): Promise<void> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/fields/${encodeURIComponent(fieldId)}/evidence-links/${encodeURIComponent(evidenceLinkId)}`,
    { method: "DELETE", headers: { ...csrfHeaders() } }
  )
  if (!res.ok && res.status !== 204) throw await toError(res)
}
