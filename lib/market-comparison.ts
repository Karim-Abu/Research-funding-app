// Market & competitor comparison client (M9I-B, same-origin BFF). Drives the
// "Markt- und Konkurrenzvergleich" section: generate, poll, read items, set item status.
// No provider/model names, no confidence percentages are ever surfaced.

import { getCsrfToken } from "./session"

export type ComparisonStatus =
  | "draft"
  | "ready_for_review"
  | "limited"
  | "insufficient_external_evidence"
  | "stale"
  | "failed"
export type ItemCategory =
  | "competitor"
  | "alternative_solution"
  | "substitute"
  | "incumbent_process"
  | "reference_solution"
  | "market_size_claim"
  | "customer_problem"
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
export type SupportStatus = "unreviewed" | "supports" | "partial" | "does_not_support"

// Analytical candidate types (Lösungslandschaft). Market statistics are never a
// candidate — they live in the market picture only.
export type CandidateType =
  | "direct_competitor"
  | "adjacent_solution"
  | "reference_infrastructure"
  | "substitute"
  | "open_source_solution"
  | "manual_or_internal_alternative"

export type CompetitionJudgmentStatus =
  | "direct_equivalent_found"
  | "similar_solutions_found"
  | "no_direct_equivalent_in_scope"
  | "insufficient_evidence"

export interface MarketPicturePointDto {
  label: string
  value: string
}

export interface MarketPictureDto {
  size_and_growth: MarketPicturePointDto[]
  segments: MarketPicturePointDto[]
  trends: MarketPicturePointDto[]
  demand_indicators: MarketPicturePointDto[]
  swiss_relevance: MarketPicturePointDto[]
  gaps: string[]
}

export interface SolutionLandscapeCandidateDto {
  item_id: string
  name: string
  candidate_type: CandidateType
  description?: string | null
  target_customer_segment?: string | null
  offering_summary?: string | null
  strengths?: string | null
  weaknesses?: string | null
  differentiation_relevance?: string | null
  relation_to_project: ItemRelation
  relevant_functions: string[]
  overlaps: string[]
  evidencing_differentiators: string[]
  unverified_differentiators: string[]
  source_document_ids: string[]
  evidence_quotes: EvidenceQuoteDto[]
  status: ItemStatus
  confidence_label: ConfidenceLabel
  support_status?: string | null
  source_scope_ok: boolean
  allowed_formulations: string[]
  disallowed_formulations: string[]
}

export interface SolutionLandscapeDto {
  candidates: SolutionLandscapeCandidateDto[]
  candidate_count_by_type: Partial<Record<CandidateType, number>>
}

export interface CompetitionJudgmentDto {
  status: CompetitionJudgmentStatus
  rationale: string
  scope_summary: string
  relevant_candidate_count: number
  key_overlaps: string[]
  evidenced_differentiators: string[]
  plausible_unverified_differentiators: string[]
  open_evidence_gaps: string[]
  allowed_formulations: string[]
  disallowed_formulations: string[]
  can_insert_into_application: boolean
}

// The user's own project idea, shown as the explicit basis of the comparison.
// `idea` is confidential (project description) — display only, never sent out.
export interface ComparisonBasisDto {
  title: string
  idea: string
  innovation_field?: string | null
  search_focus?: string | null
  search_aspects: string[]
}

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
  source_url?: string | null
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
  solution_type?: string | null
  centralization?: "centralized" | "decentralized" | "hybrid" | "unclear"
  data_access_model?: string | null
  swiss_relevance?: string | null
  core_problem_or_benefit?: string | null
  relevant_functions?: string[]
  price_business_model?: string
  uncertainty?: string | null
  relation_to_project: ItemRelation
  confidence_label: ConfidenceLabel
  status: ItemStatus
  source_document_ids: string[]
  evidence_quotes: EvidenceQuoteDto[]
  external_evidence_anchor_ids?: string[]
  cell_evidence?: Record<string, string[]>
  coverage_status?: "exact_quote_verified" | null
  support_status?: SupportStatus | null
  candidate_type?: CandidateType | null
  overlaps?: string[]
  evidencing_differentiators?: string[]
  unverified_differentiators?: string[]
  allowed_formulations?: string[]
  disallowed_formulations?: string[]
}

export interface MarketComparisonDto {
  comparison_id: string
  project_id: string
  workspace_id?: string
  status: ComparisonStatus
  comparison_version: number
  generation_status?: string | null
  research_brief_id?: string | null
  research_task_ids?: string[]
  query_approval_ids?: string[]
  source_version_ids?: string[]
  provider?: string | null
  model_ref?: string | null
  prompt_version?: string | null
  context_hash?: string | null
  stale_reason?: string | null
  consequences?: string[]
  research_gaps: string[]
  warnings: string[]
  item_count: number
  created_at: string
  updated_at: string
  error?: string | null
  items: MarketComparisonItemDto[]
  market_picture?: MarketPictureDto | null
  solution_landscape?: SolutionLandscapeDto | null
  competition_judgment?: CompetitionJudgmentDto | null
  comparison_basis?: ComparisonBasisDto | null
  scope_stale?: boolean
}

// ---------------------------------------------------------------------------
// User-facing labels (shared by the Quellen table, the editor's Markt tab and
// the market-comparison sheet). Raw enum values never reach the UI.
// ---------------------------------------------------------------------------
// RUN 4A: Vergleichsstatus in Nutzersprache für den Sektionskopf. Der Contract
// kennt kein wörtliches «complete» — der positive Zustand ist ready_for_review.
export const COMPARISON_STATUS_LABELS: Record<ComparisonStatus, string> = {
  draft: "Entwurf",
  ready_for_review: "Zur menschlichen Prüfung bereit",
  limited: "Begrenzte externe Evidenz",
  insufficient_external_evidence: "Zu wenig geeignete geprüfte Quellen",
  stale: "Veraltet — bitte neu erstellen",
  failed: "Fehlgeschlagen",
}

export const ITEM_CATEGORY_LABELS: Record<ItemCategory, string> = {
  competitor: "Konkurrent",
  alternative_solution: "Alternative Lösung",
  substitute: "Substitut",
  incumbent_process: "Bestehender Prozess",
  reference_solution: "Referenzlösung",
  market_size_claim: "Marktgrössen-Kandidat",
  customer_problem: "Kundenproblem",
  unknown: "Unklar",
}

// R8 (Anforderung 11): die fünf Abschnitte der strukturierten Zusammenfassung.
// «Offene Evidenzlücken» und «Verwendete Quellen» kommen aus research_gaps bzw.
// source_document_ids; die Item-Abschnitte gruppieren nach Kategorie.
export const SUMMARY_SECTIONS: { title: string; categories: ItemCategory[] }[] = [
  { title: "Marktgrössen-Kandidaten", categories: ["market_size_claim"] },
  {
    title: "Wettbewerber und Alternativen",
    categories: [
      "competitor",
      "alternative_solution",
      "substitute",
      "incumbent_process",
      "reference_solution",
      "unknown",
    ],
  },
  { title: "Kundenprobleme", categories: ["customer_problem"] },
]

export const ITEM_RELATION_LABELS: Record<ItemRelation, string> = {
  similar: "ähnlich",
  complementary: "komplementär",
  competing: "konkurrierend",
  reference: "Referenz",
  unclear: "unklar",
}

// R8 (Anforderungen 8+12): «Textstelle gefunden» = deterministisch verifiziertes
// Zitat (kein Fakt); «inhaltlich geprüft» entsteht erst durch die menschliche
// Übernahme (ITEM_STATUS_LABELS.accepted). Kein Claim ohne Quelle als Tatsache.
export const CONFIDENCE_LABELS: Record<ConfidenceLabel, string> = {
  source_backed: "Textstelle gefunden",
  needs_review: "Prüfung nötig",
  insufficient_evidence: "Nicht ausreichend belegt",
}

export const CONFIDENCE_STYLE: Record<ConfidenceLabel, string> = {
  source_backed: "bg-status-fulfilled/12 text-status-fulfilled",
  needs_review: "bg-status-partial/12 text-status-partial",
  insufficient_evidence: "bg-muted text-muted-foreground",
}

export const ITEM_STATUS_LABELS: Record<ItemStatus, string> = {
  proposed: "Vorgeschlagen",
  accepted: "Inhaltlich geprüft",
  rejected: "Abgelehnt",
  needs_human_review: "Prüfung nötig",
}

export const SUPPORT_STATUS_LABELS: Record<SupportStatus, string> = {
  unreviewed: "Stützung ungeprüft",
  supports: "Stützt die Aussage",
  partial: "Stützt teilweise",
  does_not_support: "Stützt die Aussage nicht",
}

export const CENTRALIZATION_LABELS: Record<NonNullable<MarketComparisonItemDto["centralization"]>, string> = {
  centralized: "zentral",
  decentralized: "dezentral",
  hybrid: "hybrid",
  unclear: "unklar",
}

// Lösungslandschaft: user-facing German labels for the analytical candidate types.
export const CANDIDATE_TYPE_LABELS: Record<CandidateType, string> = {
  direct_competitor: "Direkter Wettbewerber",
  adjacent_solution: "Angrenzende Lösung",
  reference_infrastructure: "Referenz-Infrastruktur",
  substitute: "Substitut",
  open_source_solution: "Open-Source-Lösung",
  manual_or_internal_alternative: "Manuelle/interne Alternative",
}

// Gesamturteil labels + tone (green = clear, orange = attention/limited, gray = neutral).
export const JUDGMENT_STATUS_LABELS: Record<CompetitionJudgmentStatus, string> = {
  direct_equivalent_found: "Direkt vergleichbare Lösung gefunden",
  similar_solutions_found: "Ähnliche Lösungen gefunden",
  no_direct_equivalent_in_scope: "Keine direkt gleichwertige Lösung im Suchraum",
  insufficient_evidence: "Quellenlage noch nicht ausreichend",
}

export const JUDGMENT_STATUS_TONE: Record<CompetitionJudgmentStatus, "positive" | "attention" | "neutral"> = {
  direct_equivalent_found: "attention",
  similar_solutions_found: "attention",
  no_direct_equivalent_in_scope: "positive",
  insufficient_evidence: "neutral",
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
  status: ItemStatus,
  supportStatus?: SupportStatus,
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
      body: JSON.stringify({ status, ...(supportStatus ? { support_status: supportStatus } : {}) }),
    }
  )
  if (!res.ok) throw await toError(res)
  return (await res.json()) as MarketComparisonItemDto
}
