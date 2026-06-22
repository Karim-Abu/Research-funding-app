// Source client for the live slice (same-origin BFF). Mock mode returns no live
// sources so the existing Quellen demo keeps using its own dummy data.

import { isLive } from "./app-mode"
import type { DataClassification } from "./data-classification"
import { getCsrfToken } from "./session"

export type SourceType = "pdf" | "docx" | "txt" | "url"
export type SourceStatus =
  | "uploaded"
  | "processing"
  | "processed"
  | "needs_manual_input"
  | "failed"

export interface SourceDocumentDto {
  source_id: string
  project_id: string
  name: string
  type: SourceType
  status: SourceStatus
  data_classification: DataClassification
  current_source_version_id?: string | null
  created_at?: string | null
  error_message?: string | null
}

// User-safe German copy per status (never exposes internals).
const STATUS_MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Diese Aktion ist nicht erlaubt oder durch die Datenrichtlinie blockiert.",
  409: "Die Quelle wird gerade verarbeitet oder ist in Verwendung.",
  413: "Die Datei ist zu groß.",
  415: "Dieser Dateityp wird nicht unterstützt. Erlaubt sind PDF, DOCX und TXT.",
  422: "Die Eingabe ist ungültig.",
  429: "Das Limit ist erreicht. Bitte versuchen Sie es später erneut.",
  503: "Der Dienst ist derzeit nicht verfügbar.",
}

export class SourceError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "SourceError"
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

async function toError(res: Response): Promise<SourceError> {
  let code = "error"
  try {
    const body = await res.json()
    if (body?.code) code = body.code
  } catch {
    // non-JSON body; fall back to a generic message
  }
  return new SourceError(
    res.status,
    code,
    STATUS_MESSAGES[res.status] ?? "Es ist ein Fehler aufgetreten."
  )
}

export async function listSources(
  projectId: string
): Promise<SourceDocumentDto[]> {
  if (!isLive("sources")) return []
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/sources`
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as SourceDocumentDto[]
}

export async function getSource(sourceId: string): Promise<SourceDocumentDto> {
  const res = await fetch(`/api/sources/${encodeURIComponent(sourceId)}`)
  if (!res.ok) throw await toError(res)
  return (await res.json()) as SourceDocumentDto
}

export async function uploadFiles(
  projectId: string,
  files: File[],
  classification: DataClassification
): Promise<SourceDocumentDto[]> {
  const form = new FormData()
  for (const file of files) form.append("files", file)
  form.append("data_classification_json", JSON.stringify(classification))
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/sources/files`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey(), ...csrfHeaders() },
      body: form,
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as SourceDocumentDto[]
}

export async function createTextSource(
  projectId: string,
  name: string,
  text: string,
  classification: DataClassification
): Promise<SourceDocumentDto> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/sources/text`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      body: JSON.stringify({ name, text, data_classification: classification }),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as SourceDocumentDto
}

export async function deleteSource(sourceId: string): Promise<void> {
  const res = await fetch(`/api/sources/${encodeURIComponent(sourceId)}`, {
    method: "DELETE",
    headers: { ...csrfHeaders() },
  })
  if (!res.ok && res.status !== 204) throw await toError(res)
}
