// Source client for the live slice (same-origin BFF). Mock mode returns no live
// sources so the existing Quellen demo keeps using its own dummy data.

import { isLive } from "./app-mode"
import type { DataClassification } from "./data-classification"
import { getCsrfToken } from "./session"

// Gesetzt vom Intake, wenn das Projekt angelegt wurde, aber der Upload der
// Unterlagen fehlschlug; die /quellen-Seite zeigt den Hinweis einmal und
// löscht das Flag wieder (nur ein Boolean — kein Inhalt, R4.4-konform).
export const UPLOAD_HINT_KEY = "rf_upload_hint"

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
  /** Maschinenlesbare Ursache bei failed/needs_manual_input, z. B.
   *  SOURCE_PDF_ENCRYPTED | SOURCE_NO_TEXT_LAYER | SOURCE_PARSE_FAILED. */
  error_code?: string | null
  source_url?: string | null
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

// Ursachen-spezifische Meldungen je Backend-Fehlercode. Sie gewinnen vor den
// Status-Meldungen: der Status allein kann Ursachen nicht trennen (413 ist
// «zu groß» UND «zu viele Dateien»). Die Backend-`detail`-Texte der Quellen-
// Endpunkte sind englisch und erscheinen darum nie in der Standard-UI.
const CODE_MESSAGES: Record<string, string> = {
  too_many_files:
    "Zu viele Dateien in einem Vorgang. Bitte laden Sie die Dateien in kleineren Gruppen hoch.",
  file_too_large:
    "Die Datei ist zu groß. Bitte verkleinern Sie die Datei oder teilen Sie den Inhalt auf.",
  unsupported_media_type:
    "Diese Datei wird nicht unterstützt oder der Inhalt passt nicht zur Dateiendung. Erlaubt sind PDF, DOCX und TXT.",
  invalid_classification:
    "Die Vertraulichkeits-Einstufung fehlt oder ist ungültig. Bitte prüfen Sie die Einstufung der Quelle.",
  url_import_unavailable: "Der URL-Import ist derzeit nicht verfügbar.",
  bridge_unreachable:
    "Der Analysedienst ist derzeit nicht erreichbar. Bitte versuchen Sie es später erneut.",
  network_error:
    "Der Server ist nicht erreichbar. Bitte prüfen Sie Ihre Verbindung und versuchen Sie es erneut.",
}

function resolveMessage(status: number, code: string): string {
  return (
    CODE_MESSAGES[code] ??
    STATUS_MESSAGES[status] ??
    "Es ist ein Fehler aufgetreten."
  )
}

export class SourceError extends Error {
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
    this.name = "SourceError"
    this.status = status
    this.code = code
    this.correlationId = correlationId
  }
}

function networkError(): SourceError {
  return new SourceError(0, "network_error", CODE_MESSAGES.network_error)
}

function idempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, "")
}

function csrfHeaders(): Record<string, string> {
  const csrf = getCsrfToken()
  return csrf ? { "X-CSRF-Token": csrf } : {}
}

// Fehlerkörper: FastAPI liefert application/problem+json ({code, correlation_id}),
// die Bridge selbst den Envelope {error: {code, message}}.
interface ProblemBody {
  code?: string
  correlation_id?: string
  error?: { code?: string }
}

function errorFrom(
  status: number,
  body: ProblemBody | null,
  headerCorrelation: string | null
): SourceError {
  const code = body?.code ?? body?.error?.code ?? "error"
  return new SourceError(
    status,
    code,
    resolveMessage(status, code),
    body?.correlation_id ?? headerCorrelation
  )
}

async function toError(res: Response): Promise<SourceError> {
  let body: ProblemBody | null = null
  try {
    body = (await res.json()) as ProblemBody
  } catch {
    // non-JSON body; fall back to a generic message
  }
  return errorFrom(res.status, body, res.headers.get("x-correlation-id"))
}

/** fetch mit Netzwerkfehler-Übersetzung (Server nicht erreichbar / offline). */
async function request(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch {
    throw networkError()
  }
}

export async function listSources(
  projectId: string
): Promise<SourceDocumentDto[]> {
  if (!isLive("sources")) return []
  const res = await request(
    `/api/projects/${encodeURIComponent(projectId)}/sources`
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as SourceDocumentDto[]
}

export async function getSource(sourceId: string): Promise<SourceDocumentDto> {
  const res = await request(`/api/sources/${encodeURIComponent(sourceId)}`)
  if (!res.ok) throw await toError(res)
  return (await res.json()) as SourceDocumentDto
}

export interface UploadOptions {
  /** Echter Byte-Fortschritt (0–100) des Uploads — nie für das Parsing. */
  onProgress?: (percent: number) => void
}

export function uploadFiles(
  projectId: string,
  files: File[],
  classification: DataClassification,
  options: UploadOptions = {}
): Promise<SourceDocumentDto[]> {
  const form = new FormData()
  for (const file of files) form.append("files", file)
  form.append("data_classification_json", JSON.stringify(classification))
  // XMLHttpRequest statt fetch: nur XHR liefert echte Byte-Fortschritts-Events
  // für den Upload. Fehlersemantik ist identisch (SourceError).
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open(
      "POST",
      `/api/projects/${encodeURIComponent(projectId)}/sources/files`
    )
    xhr.setRequestHeader("Idempotency-Key", idempotencyKey())
    const csrf = getCsrfToken()
    if (csrf) xhr.setRequestHeader("X-CSRF-Token", csrf)
    xhr.upload?.addEventListener("progress", (event) => {
      if (event.lengthComputable && event.total > 0) {
        options.onProgress?.(
          Math.min(100, Math.round((event.loaded / event.total) * 100))
        )
      }
    })
    xhr.addEventListener("load", () => {
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        // non-JSON body
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve((body ?? []) as SourceDocumentDto[])
        return
      }
      reject(
        errorFrom(
          xhr.status,
          body as ProblemBody | null,
          xhr.getResponseHeader("x-correlation-id")
        )
      )
    })
    xhr.addEventListener("error", () => reject(networkError()))
    xhr.addEventListener("abort", () => reject(networkError()))
    xhr.send(form)
  })
}

export async function createTextSource(
  projectId: string,
  name: string,
  text: string,
  classification: DataClassification
): Promise<SourceDocumentDto> {
  const res = await request(
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

export async function createUrlSource(
  projectId: string,
  url: string,
  name: string | null,
  classification: DataClassification,
  manualContent?: string
): Promise<SourceDocumentDto> {
  const res = await request(
    `/api/projects/${encodeURIComponent(projectId)}/sources/url`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      body: JSON.stringify({
        url,
        name,
        data_classification: classification,
        user_confirmed_public: true,
        manual_content: manualContent,
      }),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as SourceDocumentDto
}

export async function deleteSource(sourceId: string): Promise<void> {
  const res = await request(`/api/sources/${encodeURIComponent(sourceId)}`, {
    method: "DELETE",
    headers: { ...csrfHeaders() },
  })
  if (!res.ok && res.status !== 204) throw await toError(res)
}
