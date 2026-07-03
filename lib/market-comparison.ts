// Market & competitor comparison client (M9I-B, same-origin BFF). Drives the
// "Markt- und Konkurrenzvergleich" section: generate, poll, read items, set item status.
// No provider/model names, no confidence percentages are ever surfaced.

import { getCsrfToken } from "./session"

export type ComparisonStatus = "draft" | "ready_for_review" | "stale" | "failed"
export type ItemCategory =
  | "competitor"
  | "alternative_solution"
  | "substitute"
  | "incumbent_process"
  | "reference_solution"
  | "unknown"
export type ItemRelation =
  | "similar"
  | "complementary"
  | "competing"
  | "reference"
  | "unclear"
export type ConfidenceLabel =
  | "source_backed"
  | "needs_review"
  | "insufficient_evidence"
export type ItemStatus =
  | "proposed"
  | "accepted"
  | "rejected"
  | "needs_human_review"

export interface AsyncAcceptedDto {
  operation_id: string
  resource_type: string
  resource_id: string
  status: "queued" | "running"
  poll_url: string
}

export interface EvidenceQuoteDto {
  quote: string
  source_document_id: string
  source_version_id: string
  linked_evidence_anchor_id?: string | null
}

export interface MarketComparisonItemDto {
  item_id: string
  name: string
  category: ItemCategory
  description?: string | null
  target_customer_segment?: string | null
  offering_summary?: string | null
  strengths?: string | null
  weaknesses?: string | null
  differentiation_relevance?: string | null
  relation_to_project: ItemRelation
  confidence_label: ConfidenceLabel
  status: ItemStatus
  source_document_ids: string[]
  evidence_quotes: EvidenceQuoteDto[]
}

export interface MarketComparisonDto {
  comparison_id: string
  project_id: string
  status: ComparisonStatus
  comparison_version: number
  generation_status?: string | null
  research_gaps: string[]
  warnings: string[]
  item_count: number
  created_at: string
  updated_at: string
  error?: string | null
  items: MarketComparisonItemDto[]
}

// ---------------------------------------------------------------------------
// User-facing labels (shared by the Quellen table, the editor's Markt tab and
// the market-comparison sheet). Raw enum values never reach the UI.
// ---------------------------------------------------------------------------
export const ITEM_CATEGORY_LABELS: Record<ItemCategory, string> = {
  competitor: "Konkurrent",
  alternative_solution: "Alternative Lösung",
  substitute: "Substitut",
  incumbent_process: "Bestehender Prozess",
  reference_solution: "Referenzlösung",
  unknown: "Unklar",
}

export const ITEM_RELATION_LABELS: Record<ItemRelation, string> = {
  similar: "ähnlich",
  complementary: "komplementär",
  competing: "konkurrierend",
  reference: "Referenz",
  unclear: "unklar",
}

export const CONFIDENCE_LABELS: Record<ConfidenceLabel, string> = {
  source_backed: "Quelle erwähnt",
  needs_review: "Unklar — prüfen",
  insufficient_evidence: "Nicht ausreichend belegt",
}

export const CONFIDENCE_STYLE: Record<ConfidenceLabel, string> = {
  source_backed: "bg-status-fulfilled/12 text-status-fulfilled",
  needs_review: "bg-status-partial/12 text-status-partial",
  insufficient_evidence: "bg-muted text-muted-foreground",
}

export const ITEM_STATUS_LABELS: Record<ItemStatus, string> = {
  proposed: "Vorgeschlagen",
  accepted: "Übernommen",
  rejected: "Abgelehnt",
  needs_human_review: "Prüfung nötig",
}

const STATUS_MESSAGES: Record<number, string> = {
  401: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
  403: "Diese Aktion ist nicht erlaubt oder durch die Datenrichtlinie blockiert.",
  422: "Markt- und Konkurrenzvergleich ist für diese Datenklasse nicht erlaubt.",
  503: "Der Markt- und Konkurrenzvergleich ist derzeit nicht verfügbar.",
}

export class MarketComparisonError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "MarketComparisonError"
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

async function toError(res: Response): Promise<MarketComparisonError> {
  let code = "error"
  try {
    const body = await res.json()
    if (body?.code) code = body.code
  } catch {
    // non-JSON body
  }
  return new MarketComparisonError(
    res.status,
    code,
    STATUS_MESSAGES[res.status] ?? "Es ist ein Fehler aufgetreten."
  )
}

export async function createComparison(
  projectId: string
): Promise<AsyncAcceptedDto> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/market-comparisons`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey(), ...csrfHeaders() },
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as AsyncAcceptedDto
}

export async function getComparison(
  comparisonId: string
): Promise<MarketComparisonDto> {
  const res = await fetch(
    `/api/market-comparisons/${encodeURIComponent(comparisonId)}`
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as MarketComparisonDto
}

export async function getLatestComparison(
  projectId: string
): Promise<MarketComparisonDto | null> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/market-comparisons/latest`
  )
  if (!res.ok) throw await toError(res)
  const body = (await res.json()) as MarketComparisonDto | null
  return body
}

export async function updateItemStatus(
  itemId: string,
  status: ItemStatus
): Promise<MarketComparisonItemDto> {
  const res = await fetch(
    `/api/market-comparison-items/${encodeURIComponent(itemId)}/status`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
        ...csrfHeaders(),
      },
      body: JSON.stringify({ status }),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as MarketComparisonItemDto
}
