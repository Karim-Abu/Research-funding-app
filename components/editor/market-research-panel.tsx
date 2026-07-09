"use client"

// Market Research (RESEARCH.1b) — minimal UI over the existing RESEARCH.1a backend
// (deterministic query planner → Search Query Firewall → ResearchExecutor →
// Fake/Firecrawl). Flow: idle (empty state) → review (editable topic + query preview,
// from /market-research/plan) → running → results (MarketCandidate cards). Candidates
// are never facts/evidence — every card carries a human-review notice, and "Als Quelle
// speichern" reuses the existing research-result import path 1:1.

import * as React from "react"
import { ChevronDown, Loader2, ShieldAlert, Sparkles } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { importResearchResult, ResearchError } from "@/lib/research"
import {
  MarketResearchError,
  planMarketResearch,
  runMarketResearch,
  type MarketCandidateDto,
  type MarketTopicDto,
  type ProviderMode,
  type QueryCandidateDto,
} from "@/lib/market-research"

type FlowState = "idle" | "review" | "running" | "results"

const PURPOSE_LABELS: Record<string, string> = {
  market_size: "Marktgrösse",
  competitors_alternatives: "Wettbewerb",
  customer_pain: "Kundenproblem",
  go_to_market_channels: "Go-to-Market",
  pricing_willingness_to_pay: "Pricing",
}

const PROVIDER_LABELS: Record<ProviderMode, string> = {
  fake: "Test-Modus (Fake)",
  firecrawl_live: "Firecrawl (live)",
  unavailable: "nicht verfügbar",
}

const CONFIDENCE_LABELS: Record<string, string> = {
  low: "Confidence: niedrig",
  medium: "Confidence: mittel",
}

const SAFETY_COPY =
  "Research-Ergebnisse sind Quellenkandidaten, keine bestätigten Fakten. Marktangaben müssen vor Übernahme geprüft werden."

function purposeLabel(purpose: string): string {
  return PURPOSE_LABELS[purpose] ?? purpose
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

function TopicField({
  id,
  label,
  value,
  onChange,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id} className="text-[11px] text-muted-foreground">
        {label}
      </Label>
      <Input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-7 text-xs"
      />
    </div>
  )
}

function QueryPreviewRow({ query }: { query: QueryCandidateDto }) {
  return (
    <li className="rounded-md border border-border bg-background p-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-foreground">
            {purposeLabel(query.purpose)}
          </p>
          <p className="truncate text-xs text-muted-foreground">{query.query_text}</p>
        </div>
        <Badge variant={query.public_safe ? "secondary" : "destructive"} className="shrink-0">
          {query.public_safe ? "public-safe" : "needs review"}
        </Badge>
      </div>
    </li>
  )
}

function CandidateCard({
  candidate,
  onImport,
  onIgnore,
  importing,
  isImported,
}: {
  candidate: MarketCandidateDto
  onImport: () => void
  onIgnore: () => void
  importing: boolean
  isImported: boolean
}) {
  const [detailsOpen, setDetailsOpen] = React.useState(false)
  return (
    <li
      data-testid="market-candidate-card"
      className="rounded-md border border-border bg-background p-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">{candidate.title}</p>
          <p className="truncate text-xs text-muted-foreground">
            {hostOf(candidate.source_url)}
          </p>
          {candidate.snippet && (
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
              {candidate.snippet}
            </p>
          )}
        </div>
        {isImported || candidate.status === "imported" ? (
          <Badge variant="secondary" className="shrink-0">
            Als Quelle gespeichert
          </Badge>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="shrink-0"
            disabled={importing}
            onClick={onImport}
          >
            {importing ? <Loader2 className="size-3.5 animate-spin" /> : "Als Quelle speichern"}
          </Button>
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <Badge variant="outline">{purposeLabel(candidate.purpose)}</Badge>
        <Badge variant="outline">{CONFIDENCE_LABELS[candidate.confidence]}</Badge>
        <Badge variant="secondary" className="flex items-center gap-1">
          <Sparkles className="size-3" />
          Kandidat — menschliche Prüfung nötig
        </Badge>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <button
          type="button"
          onClick={() => setDetailsOpen((v) => !v)}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
        >
          <ChevronDown className={`size-3 transition-transform ${detailsOpen ? "rotate-180" : ""}`} />
          {detailsOpen ? "Details schliessen" : "Details öffnen"}
        </button>
        <button
          type="button"
          onClick={onIgnore}
          className="text-[11px] text-muted-foreground hover:underline"
        >
          Ignorieren
        </button>
      </div>
      {detailsOpen && (
        <div className="mt-2 rounded bg-muted/30 p-2 text-[11px] text-muted-foreground">
          <p>{candidate.snippet || "Kein Auszug verfügbar."}</p>
          <a
            href={candidate.source_url}
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-block break-all text-primary hover:underline"
          >
            {candidate.source_url}
          </a>
        </div>
      )}
    </li>
  )
}

export function MarketResearchPanel({
  projectId,
  onImported,
}: {
  projectId: string
  onImported?: () => void
}) {
  const [state, setState] = React.useState<FlowState>("idle")
  const [loadingPreview, setLoadingPreview] = React.useState(false)
  const [topic, setTopic] = React.useState<MarketTopicDto>({
    application_domain: "",
    technology_area: "",
    target_customers: "",
    region: "",
  })
  const [queries, setQueries] = React.useState<QueryCandidateDto[]>([])
  const [providerMode, setProviderMode] = React.useState<ProviderMode>("unavailable")
  const [candidates, setCandidates] = React.useState<MarketCandidateDto[]>([])
  const [ignored, setIgnored] = React.useState<Record<string, boolean>>({})
  const [importing, setImporting] = React.useState<Record<string, boolean>>({})
  const [imported, setImported] = React.useState<Record<string, boolean>>({})
  const [error, setError] = React.useState<string | null>(null)

  const loadPlan = React.useCallback(
    async (override?: Partial<MarketTopicDto>) => {
      setLoadingPreview(true)
      setError(null)
      try {
        const plan = await planMarketResearch(projectId, override)
        setTopic(plan.topic)
        setQueries(plan.queries)
        setProviderMode(plan.provider_mode)
        setState("review")
      } catch (err) {
        setError(
          err instanceof MarketResearchError ? err.message : "Es ist ein Fehler aufgetreten."
        )
      } finally {
        setLoadingPreview(false)
      }
    },
    [projectId]
  )

  const start = React.useCallback(() => {
    void loadPlan()
  }, [loadPlan])

  const refreshPreview = React.useCallback(() => {
    void loadPlan(topic)
  }, [loadPlan, topic])

  const runResearch = React.useCallback(async () => {
    setState("running")
    setError(null)
    try {
      const outcome = await runMarketResearch(projectId, topic)
      setCandidates(outcome.candidates)
      setIgnored({})
      setImported({})
      setState("results")
    } catch (err) {
      setError(
        err instanceof MarketResearchError ? err.message : "Es ist ein Fehler aufgetreten."
      )
      setState("review")
    }
  }, [projectId, topic])

  const cancel = React.useCallback(() => {
    setState("idle")
    setError(null)
  }, [])

  const importOne = React.useCallback(
    async (resultId: string) => {
      setImporting((m) => ({ ...m, [resultId]: true }))
      try {
        await importResearchResult(resultId)
        setImported((m) => ({ ...m, [resultId]: true }))
        onImported?.()
      } catch (err) {
        setError(
          err instanceof ResearchError ? err.message : "Die Quelle konnte nicht importiert werden."
        )
      } finally {
        setImporting((m) => ({ ...m, [resultId]: false }))
      }
    },
    [onImported]
  )

  const allQueriesBlocked = queries.length > 0 && queries.every((q) => !q.public_safe)
  const canRun = providerMode !== "unavailable" && !allQueriesBlocked
  const visibleCandidates = candidates.filter((c) => !ignored[c.result_id])

  return (
    <section data-testid="market-research-panel" className="flex flex-col gap-3">
      {state === "idle" && (
        <div data-testid="market-research-empty" className="flex flex-col gap-2">
          <Button
            variant="outline"
            size="xs"
            className="self-start"
            onClick={start}
            disabled={loadingPreview}
          >
            {loadingPreview ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              "Marktanalyse vorbereiten"
            )}
          </Button>
          {error && (
            <p role="alert" className="text-[11px] text-status-incomplete">
              {error}
            </p>
          )}
        </div>
      )}

      {state === "review" && (
        <div data-testid="market-research-review" className="flex flex-col gap-3">
          <div data-testid="market-research-topic-form" className="grid grid-cols-2 gap-2">
            <TopicField
              id="mr-domain"
              label="Anwendungsbereich"
              value={topic.application_domain}
              onChange={(v) => setTopic((t) => ({ ...t, application_domain: v }))}
            />
            <TopicField
              id="mr-technology"
              label="Technologie"
              value={topic.technology_area}
              onChange={(v) => setTopic((t) => ({ ...t, technology_area: v }))}
            />
            <TopicField
              id="mr-customers"
              label="Zielkunden"
              value={topic.target_customers}
              onChange={(v) => setTopic((t) => ({ ...t, target_customers: v }))}
            />
            <TopicField
              id="mr-region"
              label="Region"
              value={topic.region ?? ""}
              onChange={(v) => setTopic((t) => ({ ...t, region: v }))}
            />
          </div>
          <div className="flex items-center justify-between">
            <p className="text-[11px] text-muted-foreground">
              Provider-Modus: {PROVIDER_LABELS[providerMode]}
            </p>
            <Button
              type="button"
              size="xs"
              variant="ghost"
              onClick={refreshPreview}
              disabled={loadingPreview}
            >
              {loadingPreview ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                "Vorschau aktualisieren"
              )}
            </Button>
          </div>
          <ul data-testid="market-research-query-preview" className="flex flex-col gap-1.5">
            {queries.map((q) => (
              <QueryPreviewRow key={`${q.purpose}-${q.query_text}`} query={q} />
            ))}
          </ul>
          {!canRun && (
            <p className="flex items-start gap-1.5 text-[11px] text-muted-foreground">
              <ShieldAlert className="mt-0.5 size-3.5 shrink-0" />
              {providerMode === "unavailable"
                ? "Recherche ist in dieser Umgebung nicht verfügbar."
                : "Alle Suchanfragen wurden als nicht sicher eingestuft."}
            </p>
          )}
          {error && (
            <p role="alert" className="text-xs text-status-incomplete">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <Button type="button" size="sm" onClick={runResearch} disabled={!canRun}>
              Recherche starten
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={cancel}>
              Abbrechen
            </Button>
          </div>
        </div>
      )}

      {state === "running" && (
        <div data-testid="market-research-running" className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          <span>
            Recherche läuft … {queries.length} Suchanfragen · {PROVIDER_LABELS[providerMode]}
          </span>
        </div>
      )}

      {state === "results" && (
        <div data-testid="market-research-results" className="flex flex-col gap-3">
          {visibleCandidates.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Keine (weiteren) Kandidaten vorhanden.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {visibleCandidates.map((c) => (
                <CandidateCard
                  key={c.result_id}
                  candidate={c}
                  importing={!!importing[c.result_id]}
                  isImported={!!imported[c.result_id]}
                  onImport={() => importOne(c.result_id)}
                  onIgnore={() => setIgnored((m) => ({ ...m, [c.result_id]: true }))}
                />
              ))}
            </ul>
          )}
          {error && (
            <p role="alert" className="text-xs text-status-incomplete">
              {error}
            </p>
          )}
          <Button type="button" size="sm" variant="outline" className="self-start" onClick={cancel}>
            Schliessen
          </Button>
        </div>
      )}

      <p className="text-[11px] text-muted-foreground">{SAFETY_COPY}</p>
    </section>
  )
}
