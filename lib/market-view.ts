// Presentation helpers + types for the market & competition assistant on the
// Entwurf screen. Pure functions + mock-friendly types. No backend, no crawler.
// Market information is always a working hypothesis with an evidence status —
// never presented as truth.

import type {
  MarketComparisonDto,
  MarketComparisonItemDto,
} from "./market-comparison"

// ---------------------------------------------------------------------------
// Evidence/market status — distinct from requirement ("Erfüllt") and evidence
// verification ("Verifiziert") wording.
// ---------------------------------------------------------------------------
export type MarketStatus =
  | "belegt"
  | "teilweise_belegt"
  | "quelle_fehlt"
  | "pruefung_noetig"
  | "veraltet"
  | "nicht_analysiert"

export const MARKET_STATUS_LABELS: Record<MarketStatus, string> = {
  belegt: "Belegt",
  teilweise_belegt: "Teilweise belegt",
  quelle_fehlt: "Quelle fehlt",
  pruefung_noetig: "Prüfung nötig",
  veraltet: "Veraltet",
  nicht_analysiert: "Nicht analysiert",
}

export const MARKET_STATUS_STYLE: Record<MarketStatus, string> = {
  belegt: "bg-status-fulfilled/12 text-status-fulfilled",
  teilweise_belegt: "bg-status-partial/12 text-status-partial",
  quelle_fehlt: "bg-status-partial/12 text-status-partial",
  pruefung_noetig: "bg-status-partial/12 text-status-partial",
  veraltet: "bg-status-partial/12 text-status-partial",
  nicht_analysiert: "bg-muted text-muted-foreground",
}

export function marketStatusToLabel(status: MarketStatus): string {
  return MARKET_STATUS_LABELS[status]
}

export function marketStatusToStyle(status: MarketStatus): string {
  return MARKET_STATUS_STYLE[status]
}

// ---------------------------------------------------------------------------
// Optional source reference (never raw ids in the standard view).
// ---------------------------------------------------------------------------
export interface MarketSource {
  label: string
  fundstelle?: string
}

export interface MarketOverview {
  targetMarket: string
  customerSegment: string
  marketProblem: string
  customerBenefit: string
  status: MarketStatus
}

export interface CompetitorInsight {
  id: string
  name: string
  focus: string
  strength: string
  gap: string
  differentiation: string
  source: MarketSource | null
  status: MarketStatus
}

export interface DifferentiationPoint {
  id: string
  whatIsDifferent: string
  whyRelevant: string
  source: MarketSource | null
  targetField: string
  status: MarketStatus
}

export interface MarketRisk {
  title: string
  text: string
}

export interface MarketDataset {
  status: MarketStatus
  overview: MarketOverview
  competitors: CompetitorInsight[]
  differentiation: DifferentiationPoint[]
  openQuestions: string[]
  risk: MarketRisk | null
}

// ---------------------------------------------------------------------------
// Readiness summary for the status card.
// ---------------------------------------------------------------------------
export interface MarketReadiness {
  status: MarketStatus
  competitorCount: number
  sourceCount: number
  openQuestionCount: number
}

export function summarizeMarketReadiness(data: MarketDataset): MarketReadiness {
  const competitorSources = data.competitors.filter((c) => c.source).length
  const diffSources = data.differentiation.filter((d) => d.source).length
  return {
    status: data.status,
    competitorCount: data.competitors.length,
    sourceCount: competitorSources + diffSources,
    openQuestionCount: data.openQuestions.length,
  }
}

// ---------------------------------------------------------------------------
// Live comparison → market status. Pure derivation for the Markt tab header.
// ---------------------------------------------------------------------------
export function comparisonToMarketStatus(
  comparison: MarketComparisonDto | null
): MarketStatus {
  if (!comparison || comparison.status === "failed") return "nicht_analysiert"
  if (comparison.status === "stale") return "veraltet"
  if (comparison.items.length === 0) return "quelle_fehlt"
  const backed = comparison.items.filter(
    (i) => i.confidence_label === "source_backed"
  ).length
  if (backed === comparison.items.length) return "belegt"
  return backed > 0 ? "teilweise_belegt" : "quelle_fehlt"
}

/**
 * German sentence for "Als Argument übernehmen" — inserted into the LOCAL
 * editor buffer only (never auto-saved; the user reviews and saves).
 */
export function marketArgumentSentence(item: MarketComparisonItemDto): string {
  const diff = (item.differentiation_relevance ?? "").trim().replace(/\.?$/, ".")
  return `Abgrenzung zu ${item.name}: ${diff}`
}

// ---------------------------------------------------------------------------
// Relevance — market & competition matter most for Value Creation and Solution.
// ---------------------------------------------------------------------------
const MARKET_RELEVANT_SECTIONS = new Set(["value", "solution"])

export function isMarketRelevant(sectionId: string): boolean {
  return MARKET_RELEVANT_SECTIONS.has(sectionId)
}

export const MARKET_RELEVANCE_HINT =
  "Markt- und Wettbewerbsanalyse ist vor allem für «Value Creation» und «Solution» relevant. Für den aktuell gewählten Abschnitt zeigt dieser Tab deshalb keine Marktdaten — wechseln Sie in einen der beiden Abschnitte, um Marktvergleich und Marktrecherche zu nutzen."

export const MARKET_RELEVANT_EXPLAINER =
  "Dieser Abschnitt beeinflusst Marktbezug, Differenzierung und Innovationsargumentation."

export const MARKET_HYPOTHESIS_NOTE =
  "Markt- und Wettbewerbsinformationen sind Arbeitshypothesen. Verwenden Sie nur belegte Aussagen im Antrag."

// ---------------------------------------------------------------------------
// User-friendly fallbacks — never show raw ids/enums.
// ---------------------------------------------------------------------------
export const MARKET_FALLBACKS = {
  noSource: "Quelle fehlt",
  noData: "Für dieses Feld liegt noch keine Marktanalyse vor.",
  noCompetitors: "Noch keine Wettbewerber erfasst.",
  noDifferentiation: "Noch keine Differenzierungsargumente erfasst.",
  noQuestions: "Keine offenen Marktfragen.",
} as const
