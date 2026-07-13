// Market research client (RESEARCH.1b, same-origin BFF). Two synchronous calls: plan
// (topic suggestion + query preview, no side effects) and run (executes the confirmed
// topic via the existing public research vertical). No polling, no provider terminology
// surfaced beyond the generic "fake" / "firecrawl_live" / "unavailable" mode.

import { getCsrfToken } from "./session"

export type ProviderMode = "fake" | "firecrawl_live" | "unavailable"

export interface MarketTopicDto {
  application_domain: string
  technology_area: string
  target_customers: string
  region?: string | null
}

export type MarketTopicInput = Partial<MarketTopicDto>

export interface QueryCandidateDto {
  query_text: string
  purpose: string
  public_safe: boolean
  approval_required: boolean
  blocked_reason?: string | null
  // R8 Freigabepflicht: pending Freigabe je Query (Entscheid über lib/firewall.ts
  // approveSearchQuery/rejectSearchQuery). Ohne Freigabe wird die Query nie ausgeführt.
  approval_id?: string | null
}

// Deutsche Zweck-Labels für die Query-Freigabe (Dialog + Market-Panel) — rohe
// Enum-Werte erreichen die Standard-UI nie.
export const QUERY_PURPOSE_LABELS: Record<string, string> = {
  market_size: "Marktgrösse und Wachstum",
  competitors_alternatives: "Wettbewerber und Alternativen",
  customer_pain: "Kundenproblem und Bedarf",
  go_to_market_channels: "Vertriebskanäle",
  pricing_willingness_to_pay: "Zahlungsbereitschaft",
}

export function queryPurposeLabel(purpose: string): string {
  return QUERY_PURPOSE_LABELS[purpose] ?? "Marktrecherche"
}

export interface MarketResearchPlanResponse {
  topic: MarketTopicDto
  queries: QueryCandidateDto[]
  provider_mode: ProviderMode
}

export interface MarketCandidateDto {
  result_id: string
  purpose: string
  candidate_type: string
  title: string
  source_url: string
  snippet?: string | null
  confidence: "low" | "medium"
  status: "candidate" | "imported" | "rejected"
  human_review_required: boolean
}

export interface MarketResearchRunResponse {
  task_ids: string[]
  result_count: number
  tool_invocation_count: number
  credits_used: number
  candidates: MarketCandidateDto[]
  blocked_queries: number
  provider?: string | null
}

const STATUS_MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Marktrecherche ist für dieses Projekt aufgrund seiner Datenklasse gesperrt.",
  422: "Diese Anfrage kann für die aktuelle Datenklasse nicht ausgeführt werden.",
  429: "Das Limit für die Recherche ist erreicht. Bitte versuchen Sie es später erneut.",
  503: "Die Marktrecherche ist derzeit nicht verfügbar.",
}

export class MarketResearchError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "MarketResearchError"
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

async function toError(res: Response): Promise<MarketResearchError> {
  let code = "error"
  try {
    const body = await res.json()
    if (body?.code) code = body.code
  } catch {
    // non-JSON body; fall back to a generic message
  }
  return new MarketResearchError(
    res.status,
    code,
    STATUS_MESSAGES[res.status] ?? "Es ist ein Fehler aufgetreten."
  )
}

export async function planMarketResearch(
  projectId: string,
  topic?: MarketTopicInput
): Promise<MarketResearchPlanResponse> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/market-research/plan`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify(topic ?? {}),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as MarketResearchPlanResponse
}

// R8: eine bearbeitete Query erneut durch die Firewall prüfen lassen — liefert den
// bereinigten Text (nur dieser würde ausgeführt) + eine neue pending Freigabe. Die
// alte Freigabe lehnt der Aufrufer via rejectSearchQuery ab.
export async function previewMarketQuery(
  projectId: string,
  queryText: string,
  purpose?: string
): Promise<QueryCandidateDto> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/market-research/queries/preview`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      body: JSON.stringify({ query_text: queryText, purpose: purpose ?? null }),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as QueryCandidateDto
}

export async function runMarketResearch(
  projectId: string,
  topic: MarketTopicDto,
  approvalIds: string[]
): Promise<MarketResearchRunResponse> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/market-research/run`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      // R8 Freigabepflicht: nur freigegebene Queries werden ausgeführt.
      body: JSON.stringify({ ...topic, approval_ids: approvalIds }),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as MarketResearchRunResponse
}
