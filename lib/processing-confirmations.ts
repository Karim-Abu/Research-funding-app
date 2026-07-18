// Processing-confirmation client (Milestone 9D.2; erweitert in R4.3). A per-run
// user acknowledgement: "cloud_assisted" = public/synthetic content may be sent
// to the configured cloud AI; "local_only" = KI-Opt-in für interne/vertrauliche
// Projekte über den lokalen Verarbeitungspfad (Warnung verstanden). Same-origin BFF.

import { getCsrfToken } from "./session"
import { RunError } from "./runs"

export const POLICY_VERSION = "1.1.0"

export type ConfirmationProcessingMode = "cloud_assisted" | "local_only" | "live"

export interface ProcessingConfirmationCreate {
  processing_mode: ConfirmationProcessingMode
  source_version_ids: string[]
  accepted_policy_version: string
  purpose: string
  expires_after_one_run: true
}

export interface ProcessingConfirmationDto {
  confirmation_id: string
  project_id: string
  created_by: string
  status: "valid" | "used" | "revoked" | "expired"
  source_version_ids: string[]
  policy_version: string
  created_at: string
}

const STATUS_MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Sie haben für dieses Projekt keine Berechtigung, diese Aktion auszuführen.",
  422: "Cloud-KI ist nur für öffentliche oder synthetische Inhalte verfügbar.",
  503: "Der Dienst ist derzeit nicht verfügbar.",
}

function idempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, "")
}

function csrfHeaders(): Record<string, string> {
  const csrf = getCsrfToken()
  return csrf ? { "X-CSRF-Token": csrf } : {}
}

async function toError(res: Response): Promise<RunError> {
  let code = "error"
  try {
    const body = await res.json()
    if (body?.code) code = body.code
  } catch {
    // non-JSON body
  }
  return new RunError(
    res.status,
    code,
    STATUS_MESSAGES[res.status] ?? "Die Cloud-Freigabe konnte nicht erstellt werden."
  )
}

export async function createProcessingConfirmation(
  projectId: string,
  sourceVersionIds: string[],
  purpose = "KI-Vorschläge für Textentwürfe vorbereiten",
  processingMode: ConfirmationProcessingMode = "cloud_assisted"
): Promise<ProcessingConfirmationDto> {
  const payload: ProcessingConfirmationCreate = {
    processing_mode: processingMode,
    source_version_ids: sourceVersionIds,
    accepted_policy_version: POLICY_VERSION,
    purpose,
    expires_after_one_run: true,
  }
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/processing-confirmations`,
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
  return (await res.json()) as ProcessingConfirmationDto
}
