// Integrated-Draft demo client (DEMO.1). Talks to the demo view routes:
// POST /api/demo/integrated-draft (fake-only run → DraftPackage) and
// GET /api/demo/integrated-draft/real (whitelist read view over existing
// R5.9-REAL artifacts — never triggers a new provider call).

import { getCsrfToken } from "./session"
import type { GenerationKind } from "./generation-kind"

export type FieldDraftStatus =
  | "generated"
  | "deterministic"
  | "missing_inputs"
  | "skipped"
  | "unavailable"
  | "failed"

export interface MissingInputDto {
  label: string
  reason?: string | null
}

export interface FieldDraftItemDto {
  field_id: string
  field_label: string
  status: FieldDraftStatus
  suggestion_text: string | null
  generation_kind: GenerationKind | null
  missing_inputs: MissingInputDto[]
  provider: string | null
  model: string | null
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  latency_ms: number | null
  cost_status: string | null
  human_review_required: boolean
}

export interface UsageSummaryDto {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  usage_record_count: number
  cost_status_counts: Record<string, number>
}

export interface ResearchUsageDto {
  used: boolean
  candidates: number
  imported_sources: number
}

export interface DraftPackageDto {
  package_id: string
  case_id: string
  created_at: string
  provider_mode: string
  data_mode: string
  fields: FieldDraftItemDto[]
  usage_summary: UsageSummaryDto
  research_summary: { market: ResearchUsageDto; partner: ResearchUsageDto }
  human_review_required: boolean
}

// Real-run artifacts (R5.9-REAL whitelist report part — previews only).
export interface RealRunFieldDto {
  field_id: string
  status: string
  provider: string | null
  model: string | null
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  latency_ms: number | null
  cost_status: string | null
  missing_inputs_count: number
  human_review_required: boolean
  suggestion_preview: string
}

export interface RealRunReportDto {
  provider: string
  data_mode: string
  created_at: string
  fields: RealRunFieldDto[]
  usage_summary: UsageSummaryDto
}

export interface RealRunsDto {
  providers: Record<string, RealRunReportDto>
}

export class IntegratedDraftError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = "IntegratedDraftError"
    this.status = status
  }
}

const MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Diese Aktion ist nicht erlaubt.",
  503: "Der Demo-Modus ist auf dem Server nicht aktiviert.",
}

async function toError(res: Response): Promise<IntegratedDraftError> {
  return new IntegratedDraftError(
    res.status,
    MESSAGES[res.status] ?? "Der Antragsentwurf konnte nicht geladen werden."
  )
}

function csrfHeaders(): Record<string, string> {
  const csrf = getCsrfToken()
  return csrf ? { "X-CSRF-Token": csrf } : {}
}

/** Fake/Demo only — the backend refuses (503) unless the fake provider is on. */
export async function generateDemoDraft(): Promise<DraftPackageDto> {
  const res = await fetch("/api/demo/integrated-draft", {
    method: "POST",
    headers: { ...csrfHeaders() },
  })
  if (!res.ok) throw await toError(res)
  return (await res.json()) as DraftPackageDto
}

/** Read-only: already generated real-run artifacts; never a new provider call. */
export async function getRealRunArtifacts(): Promise<RealRunsDto> {
  const res = await fetch("/api/demo/integrated-draft/real")
  if (!res.ok) throw await toError(res)
  return (await res.json()) as RealRunsDto
}
