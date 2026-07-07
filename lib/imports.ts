// R3.3 — Client für den Innolink-Antragsimport (same-origin BFF).
// Upload läuft über lib/sources.ts (bestehender Quellen-Pfad); hier: Mapping
// einer verarbeiteten Quelle auf Portal-Felder + HITL-Entscheidungen.

import { getCsrfToken } from "./session"

export type ImportConfidence = "found" | "uncertain"
export type ImportDecision =
  | "pending"
  | "conflict"
  | "accepted"
  | "saved_as_source"
  | "ignored"

export interface ImportCandidateDto {
  import_candidate_id: string
  source_id: string
  field_id: string
  /** Deutsches Anzeige-Label — die UI zeigt nie rohe Feld-IDs. */
  label: string
  extracted_text: string
  confidence: ImportConfidence
  source_location: string | null
  decision: ImportDecision
  decided_at: string | null
  accepted_draft_version_id: string | null
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
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "ImportError"
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

async function toError(res: Response): Promise<ImportError> {
  let code = "error"
  let detail: string | null = null
  try {
    const body = await res.json()
    if (body?.code) code = body.code
    // Backend-Problem-Details sind bereits deutsche, nutzerlesbare Sätze.
    if (typeof body?.detail === "string" && body.detail) detail = body.detail
  } catch {
    // non-JSON body
  }
  return new ImportError(
    res.status,
    code,
    detail ?? STATUS_MESSAGES[res.status] ?? "Es ist ein Fehler aufgetreten."
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
    run_id?: string
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
