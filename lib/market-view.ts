// Presentation helpers + types for the market & competition assistant on the
// Entwurf screen. Pure functions + mock-friendly types. No backend, no crawler.
// Market information is always a working hypothesis with an evidence status —
// never presented as truth.

import {
  CANDIDATE_TYPE_LABELS,
  ITEM_CATEGORY_LABELS,
  JUDGMENT_STATUS_TONE,
} from "./market-comparison"
import type {
  CandidateType,
  CompetitionJudgmentStatus,
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
// EIN ehrliches Status-Viewmodel für alle drei Markt-Oberflächen (Quellen-Karte,
// Editor-Rail, Sheet). Ersetzt die divergierenden Ableitungen, die „Fehlgeschlagen"
// und „Nicht analysiert" gleichzeitig zeigen konnten. (2026-07-24)
// ---------------------------------------------------------------------------
export type MarketTone = "neutral" | "positive" | "attention" | "error"

export interface MarketWorkspaceStatus {
  label: string
  tone: MarketTone
  /** Kurzer nächster Schritt / Grund — nur wenn hilfreich. */
  hint?: string
}

export const MARKET_TONE_STYLE: Record<MarketTone, string> = {
  neutral: "bg-muted text-muted-foreground",
  positive: "bg-status-fulfilled/12 text-status-fulfilled",
  attention: "bg-status-partial/12 text-status-partial",
  error: "bg-destructive/12 text-destructive",
}

export function marketWorkspaceStatus(
  comparison: MarketComparisonDto | null
): MarketWorkspaceStatus {
  if (!comparison) return { label: "Noch nicht erstellt", tone: "neutral" }
  const hasItems = comparison.items.length > 0
  switch (comparison.status) {
    case "failed":
      return {
        label: "Letzter Versuch fehlgeschlagen",
        tone: "error",
        hint: "Bitte erneut erstellen.",
      }
    case "insufficient_external_evidence":
      return {
        label: "Zu wenige geprüfte Quellen",
        tone: "attention",
        hint: "Mindestens zwei geeignete öffentliche Quellen nötig.",
      }
    case "limited":
      return {
        label: "Begrenzte Evidenz",
        tone: "attention",
        hint: hasItems
          ? undefined
          : "Marktinformationen vorhanden, aber noch kein belastbarer Vergleich.",
      }
    case "stale":
      return { label: "Veraltet — neu erstellen", tone: "attention" }
    case "draft":
      return { label: "Wird erstellt …", tone: "neutral" }
    case "ready_for_review":
      return hasItems
        ? { label: "Zur Prüfung bereit", tone: "positive" }
        : {
            label: "Keine belegten Einträge",
            tone: "attention",
            hint: "Es wurden keine quellengestützten Vergleichseinträge gefunden.",
          }
    default:
      return { label: "Noch nicht erstellt", tone: "neutral" }
  }
}

// ---------------------------------------------------------------------------
// Marktbild — beantwortet die vier/fünf Kernfragen ausschliesslich aus
// quellengestützten Einträgen (keine unbelegten Claims, CLAUDEX §7). Reine
// Ableitung fürs Sheet und (gekürzt) die Editor-Rail. (2026-07-24)
// ---------------------------------------------------------------------------
export interface MarketPicturePoint {
  label: string
  value: string
}

export interface MarketPicture {
  points: MarketPicturePoint[]
  gaps: string[]
  hasContent: boolean
}

// Kategorien, die eine „Lösungsart/Anbieter" darstellen (nicht Marktsignal/Problem).
const SOLUTION_CATEGORIES = new Set([
  "competitor",
  "alternative_solution",
  "substitute",
  "incumbent_process",
  "reference_solution",
  "unknown",
])

function joinDistinct(values: (string | null | undefined)[], limit: number): string {
  const seen: string[] = []
  for (const raw of values) {
    const value = (raw ?? "").trim()
    if (value && !seen.includes(value)) seen.push(value)
  }
  if (seen.length === 0) return ""
  const shown = seen.slice(0, limit).join(" · ")
  return seen.length > limit ? `${shown} …` : shown
}

export function deriveMarketPicture(
  comparison: MarketComparisonDto | null
): MarketPicture {
  const backed =
    comparison?.items.filter((i) => i.confidence_label === "source_backed") ?? []
  const points: MarketPicturePoint[] = []

  // 1) Lösungsarten / Anbieter — Anzahl je Kategorie (nur echte Lösungskategorien).
  const byCategory = new Map<string, number>()
  for (const item of backed) {
    if (!SOLUTION_CATEGORIES.has(item.category)) continue
    byCategory.set(item.category, (byCategory.get(item.category) ?? 0) + 1)
  }
  if (byCategory.size > 0) {
    const value = [...byCategory.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([category, count]) => `${ITEM_CATEGORY_LABELS[category as keyof typeof ITEM_CATEGORY_LABELS] ?? category} (${count})`)
      .join(" · ")
    points.push({ label: "Lösungsarten", value })
  }

  // 2) Kundengruppen — belegte Zielsegmente.
  const segments = joinDistinct(backed.map((i) => i.target_customer_segment), 3)
  if (segments) points.push({ label: "Kundengruppen", value: segments })

  // 3) Typische Funktionen — Vereinigung der belegten Funktionslisten.
  const functions = joinDistinct(
    backed.flatMap((i) => i.relevant_functions ?? []),
    5
  )
  if (functions) points.push({ label: "Typische Funktionen", value: functions })

  // 4) Marktsignale/Trends — belegte Marktgrössen-Aussagen (Namen).
  const signals = joinDistinct(
    backed.filter((i) => i.category === "market_size_claim").map((i) => i.name),
    3
  )
  if (signals) points.push({ label: "Marktsignale", value: signals })

  // 5) Kundenprobleme — belegte Problem-Aussagen (Namen).
  const problems = joinDistinct(
    backed.filter((i) => i.category === "customer_problem").map((i) => i.name),
    3
  )
  if (problems) points.push({ label: "Kundenprobleme", value: problems })

  const gaps = comparison?.research_gaps ?? []
  return { points, gaps, hasContent: points.length > 0 || gaps.length > 0 }
}

// ---------------------------------------------------------------------------
// Gesamturteil / Lösungslandschaft helpers (backend-derived, read-time). The
// backend competition_judgment / solution_landscape / market_picture are the
// single source of truth; these helpers only translate them for display.
// ---------------------------------------------------------------------------
export function candidateTypeLabel(type: CandidateType): string {
  return CANDIDATE_TYPE_LABELS[type]
}

export function judgmentToneClass(status: CompetitionJudgmentStatus): string {
  return MARKET_TONE_STYLE[JUDGMENT_STATUS_TONE[status]]
}

/**
 * Market picture for the compact rail. Prefers the backend market_picture and
 * falls back to the client-side derivation for older responses without it.
 */
export function marketPictureFrom(comparison: MarketComparisonDto | null): MarketPicture {
  const backend = comparison?.market_picture
  if (!backend) return deriveMarketPicture(comparison)
  const points: MarketPicturePoint[] = []
  const push = (label: string, values: { value: string }[]) => {
    const value = joinDistinct(values.map((p) => p.value), 4)
    if (value) points.push({ label, value })
  }
  push("Marktgrösse & Wachstum", backend.size_and_growth)
  push("Segmente", backend.segments)
  push("Trends", backend.trends)
  push("Nachfrage", backend.demand_indicators)
  push("Schweiz-Relevanz", backend.swiss_relevance)
  const gaps = backend.gaps ?? []
  return { points, gaps, hasContent: points.length > 0 || gaps.length > 0 }
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
