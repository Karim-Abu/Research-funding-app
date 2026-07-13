// Run client for the live v1.1 slice (same-origin BFF). The user-facing
// "Analyse starten" action stays capability-gated until M4; this client is
// exercised by tests and the API smoke. Mock mode keeps its own engine.

import { getCsrfToken } from "./session"

export type RunStatus =
  | "created"
  | "running"
  | "paused_for_review"
  | "completed"
  | "stopped"
  | "failed"
  | "cancelled"
export type ProcessingMode = "deterministic_only" | "cloud_assisted" | "local_only"

export interface RunSettings {
  processing_mode: ProcessingMode
  max_cost_chf: number
  max_llm_calls: number
  max_web_calls: number
  source_version_ids?: string[]
  /** References a one-run cloud-processing confirmation for a cloud_assisted run. */
  internal_cloud_confirmation_id?: string
}

export interface AnalysisRunDto {
  run_id: string
  project_id: string
  status: RunStatus
  current_stage: string
  progress_percent: number
  processing_mode: ProcessingMode
  created_at: string
  recheck_required: boolean
  semantic_findings_stale: boolean
  started_at?: string | null
  ended_at?: string | null
  stop_reason?: string | null
}

export interface RunListDto {
  items: AnalysisRunDto[]
  next_cursor?: string | null
}

export interface AsyncAcceptedDto {
  operation_id: string
  resource_type: string
  resource_id: string
  status: "queued" | "running"
  poll_url: string
}

const STATUS_MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Diese Aktion ist nicht erlaubt oder durch die Datenrichtlinie blockiert.",
  409: "Für dieses Projekt läuft bereits eine Analyse.",
  422: "Es ist keine verarbeitete Quelle für eine Analyse verfügbar.",
  429: "Das Limit ist erreicht. Bitte versuchen Sie es später erneut.",
  503: "Der Dienst ist derzeit nicht verfügbar.",
}

export class RunError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "RunError"
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
    STATUS_MESSAGES[res.status] ?? "Es ist ein Fehler aufgetreten."
  )
}

export async function createRun(
  projectId: string,
  settings: RunSettings
): Promise<AsyncAcceptedDto> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/runs`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      body: JSON.stringify({ settings }),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as AsyncAcceptedDto
}

export async function listProjectRuns(
  projectId: string
): Promise<AnalysisRunDto[]> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/runs`)
  if (!res.ok) throw await toError(res)
  return ((await res.json()) as RunListDto).items
}

export async function getRun(runId: string): Promise<AnalysisRunDto> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}`)
  if (!res.ok) throw await toError(res)
  return (await res.json()) as AnalysisRunDto
}

export async function cancelRun(runId: string): Promise<AnalysisRunDto> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey(), ...csrfHeaders() },
  })
  if (!res.ok) throw await toError(res)
  return (await res.json()) as AnalysisRunDto
}

// --- Persistierte Run-Phasen (GET /runs/{id}/phases) -------------------------
// Reload-sicherer Phasenstand + technische Zusammenfassung. Kein erfundener
// Fortschritt: die Werte kommen 1:1 aus der Datenbank des Laufs.

export type RunPhaseKey =
  | "prepare_documents"
  | "detect_facts"
  | "formal_checks"
  | "web_research"
  | "draft_fields"
  | "quality_review"

export type RunPhaseStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "skipped"

export interface RunPhaseDto {
  phase_key: RunPhaseKey
  status: RunPhaseStatus
  started_at?: string | null
  ended_at?: string | null
  error_code?: string | null
  detail: Record<string, unknown>
}

export interface AgentUsageSummaryDto {
  agent_id: string
  invocations: number
  providers: string[]
  models: string[]
  input_tokens: number
  output_tokens: number
  priced_cost_chf: number
  has_unpriced_usage: boolean
  latency_ms_total: number
}

export interface RunTechnicalSummaryDto {
  run_id: string
  agents: AgentUsageSummaryDto[]
  priced_cost_chf_total: number
  has_unpriced_usage: boolean
  same_provider_a2_a3?: boolean | null
}

export interface RunPhasesDto {
  run_id: string
  run_status: RunStatus
  phases: RunPhaseDto[]
  technical: RunTechnicalSummaryDto
}

export async function getRunPhases(runId: string): Promise<RunPhasesDto> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/phases`)
  if (!res.ok) throw await toError(res)
  return (await res.json()) as RunPhasesDto
}
