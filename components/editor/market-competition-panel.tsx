"use client"

import * as React from "react"
import { Info, AlertTriangle, ArrowRight, Plus, Circle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { LiveMarketComparison } from "@/components/editor/live-market-comparison"
import { cn } from "@/lib/utils"
import {
  MARKET_STATUS_LABELS,
  MARKET_STATUS_STYLE,
  MARKET_FALLBACKS,
  MARKET_RELEVANCE_HINT,
  MARKET_RELEVANT_EXPLAINER,
  MARKET_HYPOTHESIS_NOTE,
  summarizeMarketReadiness,
  type MarketDataset,
  type MarketSource,
  type MarketStatus,
} from "@/lib/market-view"

const ACTION_HINT = "Im Mock-Modus lokal simuliert · echte Marktanalyse folgt später."

function StatusChip({ status }: { status: MarketStatus }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
        MARKET_STATUS_STYLE[status]
      )}
    >
      {MARKET_STATUS_LABELS[status]}
    </span>
  )
}

function SourceLine({
  source,
  onAddSource,
}: {
  source: MarketSource | null
  onAddSource: () => void
}) {
  if (!source) {
    return (
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] text-muted-foreground">{MARKET_FALLBACKS.noSource}</span>
        <button
          type="button"
          onClick={onAddSource}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
        >
          <Plus className="size-3" />
          Quelle hinzufügen
        </button>
      </div>
    )
  }
  return (
    <p className="text-[11px] text-muted-foreground">
      Quelle: {source.label}
      {source.fundstelle ? ` · ${source.fundstelle}` : ""}
    </p>
  )
}

interface MarketCompetitionPanelProps {
  data: MarketDataset | null
  relevant: boolean
  /** Live mode has no real market analysis yet → show empty state, no mock data. */
  live?: boolean
  /** Live project id → render the compact, read-only M9I-B comparison context. */
  projectId?: string
  /** Append a sentence + improvement label to the current KI suggestion (mock). */
  onApply?: (improvement: string, text: string) => void
}

export function MarketCompetitionPanel({
  data,
  relevant,
  live = false,
  projectId,
  onApply,
}: MarketCompetitionPanelProps) {
  const [note, setNote] = React.useState<string | null>(null)
  const [markedRisk, setMarkedRisk] = React.useState(false)

  function localAction() {
    setNote(ACTION_HINT)
  }

  if (!relevant) {
    return (
      <p className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-3 py-2.5 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-4 shrink-0" />
        {MARKET_RELEVANCE_HINT}
      </p>
    )
  }

  if (!data) {
    // M9I-B: a live project shows the compact, read-only public-source comparison.
    if (live && projectId) {
      return <LiveMarketComparison projectId={projectId} />
    }
    if (live) {
      return (
        <div className="flex flex-col gap-3">
          <p className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground">
            <Info className="mt-0.5 size-3.5 shrink-0" />
            {MARKET_RELEVANT_EXPLAINER}
          </p>
          <div>
            <p className="text-sm font-medium text-foreground">Noch keine Marktanalyse vorhanden</p>
            <p className="text-xs text-muted-foreground">
              Für eine Markt- und Wettbewerbsanalyse benötigt das System
              Projektbeschreibung, relevante Quellen und optional bekannte
              Wettbewerber.
            </p>
          </div>
          <ul className="flex flex-col gap-1">
            {[
              "Projektidee vorhanden",
              "Markt- oder Konkurrenzquellen vorhanden",
              "bekannte Wettbewerber angegeben",
            ].map((item) => (
              <li key={item} className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <Circle className="size-3 shrink-0" />
                {item}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="xs" render={<a href="/quellen" />} nativeButton={false}>
              Quelle hinzufügen
            </Button>
            <Button variant="outline" size="xs" disabled>
              Offene Marktfrage erstellen
            </Button>
            <Button variant="outline" size="xs" disabled>
              Marktanalyse vorbereiten
            </Button>
          </div>
          <p className="text-[11px] text-muted-foreground">
            „Marktanalyse vorbereiten" ist noch nicht verfügbar.
          </p>
        </div>
      )
    }
    return (
      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted-foreground">{MARKET_FALLBACKS.noData}</p>
        <Button variant="outline" size="sm" onClick={localAction} className="self-start">
          Marktanalyse aktualisieren
        </Button>
        {note && <p className="text-[11px] text-muted-foreground">{note}</p>}
      </div>
    )
  }

  const readiness = summarizeMarketReadiness(data)
  const firstBelegtDiff =
    data.differentiation.find((d) => d.status === "belegt") ?? data.differentiation[0]

  return (
    <div className="flex flex-col gap-5">
      <p className="text-[11px] text-muted-foreground">{MARKET_RELEVANT_EXPLAINER}</p>
      {/* Hypothesis note */}
      <p className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" />
        {MARKET_HYPOTHESIS_NOTE}
      </p>

      {/* A) Market status card */}
      <section className="flex flex-col gap-2 rounded-lg border border-border bg-card px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <h4 className="text-xs font-semibold text-foreground">Marktstatus</h4>
          <StatusChip status={data.status} />
        </div>
        <dl className="grid grid-cols-3 gap-2 text-center">
          <div>
            <dd className="text-base font-semibold text-foreground">{readiness.competitorCount}</dd>
            <dt className="text-[10px] text-muted-foreground">Wettbewerber</dt>
          </div>
          <div>
            <dd className="text-base font-semibold text-foreground">{readiness.sourceCount}</dd>
            <dt className="text-[10px] text-muted-foreground">Quellen</dt>
          </div>
          <div>
            <dd className="text-base font-semibold text-foreground">{readiness.openQuestionCount}</dd>
            <dt className="text-[10px] text-muted-foreground">Offene Fragen</dt>
          </div>
        </dl>
      </section>

      {/* B) Market overview */}
      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Marktüberblick
          </h4>
          <StatusChip status={data.overview.status} />
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-muted-foreground">Zielmarkt</dt>
          <dd className="text-foreground">{data.overview.targetMarket}</dd>
          <dt className="text-muted-foreground">Zielkunden</dt>
          <dd className="text-foreground">{data.overview.customerSegment}</dd>
          <dt className="text-muted-foreground">Marktproblem</dt>
          <dd className="text-foreground">{data.overview.marketProblem}</dd>
          <dt className="text-muted-foreground">Kundennutzen</dt>
          <dd className="text-foreground">{data.overview.customerBenefit}</dd>
        </dl>
      </section>

      {/* C) Competitor comparison */}
      <section className="flex flex-col gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Wettbewerbervergleich
        </h4>
        {data.competitors.length === 0 ? (
          <p className="text-xs text-muted-foreground">{MARKET_FALLBACKS.noCompetitors}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {data.competitors.map((c) => (
              <li key={c.id} className="flex flex-col gap-1.5 rounded-md border border-border px-3 py-2.5">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-semibold text-foreground">{c.name}</span>
                  <StatusChip status={c.status} />
                </div>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[11px]">
                  <dt className="text-muted-foreground">Fokus</dt>
                  <dd className="text-foreground">{c.focus}</dd>
                  <dt className="text-muted-foreground">Stärke</dt>
                  <dd className="text-foreground">{c.strength}</dd>
                  <dt className="text-muted-foreground">Lücke</dt>
                  <dd className="text-foreground">{c.gap}</dd>
                  <dt className="text-muted-foreground">Differenzierung</dt>
                  <dd className="text-foreground">{c.differentiation}</dd>
                </dl>
                <SourceLine source={c.source} onAddSource={localAction} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* D) Differentiation / USP */}
      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Differenzierung
          </h4>
          {firstBelegtDiff && (
            <button
              type="button"
              onClick={() =>
                onApply?.("Marktargument ergänzt", `${firstBelegtDiff.whatIsDifferent}. ${firstBelegtDiff.whyRelevant}.`)
              }
              className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
            >
              Marktargument übernehmen
              <ArrowRight className="size-3" />
            </button>
          )}
        </div>
        {data.differentiation.length === 0 ? (
          <p className="text-xs text-muted-foreground">{MARKET_FALLBACKS.noDifferentiation}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {data.differentiation.map((d) => (
              <li key={d.id} className="flex flex-col gap-1 rounded-md border border-border px-3 py-2.5">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-medium text-foreground">{d.whatIsDifferent}</span>
                  <StatusChip status={d.status} />
                </div>
                <p className="text-[11px] text-muted-foreground">{d.whyRelevant}</p>
                <p className="text-[11px] text-muted-foreground">Passt zu: {d.targetField}</p>
                <SourceLine source={d.source} onAddSource={localAction} />
                <button
                  type="button"
                  onClick={() => onApply?.("Differenzierung ergänzt", `${d.whatIsDifferent}. ${d.whyRelevant}.`)}
                  className="mt-0.5 inline-flex w-fit items-center gap-1 text-[11px] font-medium text-primary hover:underline"
                >
                  In KI-Vorschlag übernehmen
                  <ArrowRight className="size-3" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* E) Risk card */}
      {data.risk && (
        <section className="flex flex-col gap-2 rounded-lg border border-status-partial/30 bg-status-partial/8 px-4 py-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-4 shrink-0 text-status-partial" />
            <h4 className="text-xs font-semibold text-foreground">{data.risk.title}</h4>
          </div>
          <p className="text-[11px] text-foreground">{data.risk.text}</p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              size="xs"
              variant="outline"
              onClick={() => setMarkedRisk(true)}
              disabled={markedRisk}
            >
              {markedRisk ? "Als offene Frage markiert" : "Als offene Frage markieren"}
            </Button>
            <Button
              size="xs"
              onClick={() =>
                onApply?.(
                  "Konkurrenzabgrenzung ergänzt",
                  "Gegenüber identifizierten Lösungen liegt die Differenzierung in der nachweisbar niedrigeren Prozesstemperatur und höheren Recyclingfähigkeit."
                )
              }
            >
              Konkurrenzabgrenzung einbauen
            </Button>
          </div>
        </section>
      )}

      {/* F) Open market questions */}
      <section className="flex flex-col gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Offene Marktfragen
        </h4>
        {data.openQuestions.length === 0 ? (
          <p className="text-xs text-muted-foreground">{MARKET_FALLBACKS.noQuestions}</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {data.openQuestions.map((q) => (
              <li key={q} className="text-[11px] text-foreground">
                • {q}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Tab actions (local simulation) */}
      <div className="flex flex-wrap gap-2 border-t border-border pt-3">
        <Button size="xs" variant="outline" onClick={localAction}>
          Marktanalyse aktualisieren
        </Button>
        <Button size="xs" variant="outline" onClick={localAction}>
          Konkurrenzvergleich erstellen
        </Button>
      </div>
      {note && <p className="text-[11px] text-muted-foreground">{note}</p>}
    </div>
  )
}
