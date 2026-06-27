// Export client (live Milestone 8 slice). Deterministic DOCX/Markdown/technical
// evidence artifacts. Mirrors the openapi ExportCreate / ExportArtifact shapes.
// draft_marked from the returned artifact is authoritative after creation.

import { getCsrfToken } from "./session"
import { pollOperation } from "./operations"

export type ExportType = "docx" | "markdown" | "technical_evidence"
export type ExportStatus = "queued" | "generating" | "available" | "failed"

export interface ExportArtifactDto {
  export_id: string
  run_id: string
  type: ExportType
  status: ExportStatus
  draft_marked: boolean
  filename?: string | null
  created_at?: string | null
}

export class ExportError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "ExportError"
    this.status = status
    this.code = code
  }
}

const MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Diese Aktion ist nicht erlaubt.",
  404: "Der Export wurde nicht gefunden.",
  409: "Der Export ist noch nicht bereit.",
  429: "Das Export-Limit für diesen Lauf und dieses Format ist erreicht.",
}

function idempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, "")
}

function csrfHeaders(): Record<string, string> {
  const csrf = getCsrfToken()
  return csrf ? { "X-CSRF-Token": csrf } : {}
}

async function toError(res: Response): Promise<ExportError> {
  let code = "error"
  let detail = ""
  try {
    const body = await res.json()
    if (body?.code) code = body.code
    if (typeof body?.detail === "string") detail = body.detail
  } catch {
    /* non-JSON */
  }
  return new ExportError(res.status, code, detail || MESSAGES[res.status] || "Es ist ein Fehler aufgetreten.")
}

export async function getExport(exportId: string): Promise<ExportArtifactDto> {
  const res = await fetch(`/api/exports/${encodeURIComponent(exportId)}`)
  if (!res.ok) throw await toError(res)
  return (await res.json()) as ExportArtifactDto
}

/** Create an export, poll the async operation, and resolve the final artifact. */
export async function createExport(
  runId: string,
  type: ExportType,
  forceDraft = false
): Promise<ExportArtifactDto> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/exports`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey(),
      ...csrfHeaders(),
    },
    body: JSON.stringify({ type, force_draft: forceDraft }),
  })
  if (!res.ok) throw await toError(res)
  const accepted = (await res.json()) as { operation_id: string; resource_id: string }
  await new Promise<void>((resolve, reject) => {
    pollOperation(accepted.operation_id, {
      onTerminal: (op) => {
        if (op.status === "succeeded") resolve()
        else reject(new ExportError(500, "export_failed", "Export fehlgeschlagen."))
      },
    })
  })
  return getExport(accepted.resource_id)
}

function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback
  const match = /filename="?([^";]+)"?/i.exec(header)
  return match ? match[1] : fallback
}

/** Download a finished export and trigger a browser save. */
export async function downloadExport(artifact: ExportArtifactDto): Promise<void> {
  const res = await fetch(
    `/api/exports/${encodeURIComponent(artifact.export_id)}/download`
  )
  if (!res.ok) throw await toError(res)
  const blob = await res.blob()
  const filename = filenameFromDisposition(
    res.headers.get("content-disposition"),
    artifact.filename || `${artifact.export_id}.bin`
  )
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
