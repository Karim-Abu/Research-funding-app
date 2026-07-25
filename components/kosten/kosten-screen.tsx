"use client"

import * as React from "react"
import { ChevronDown, CircleDollarSign, Clock3, Info, Layers3, WalletCards } from "lucide-react"
import { RunStatusBadge } from "@/components/kosten/run-status-badge"
import { Badge } from "@/components/ui/badge"
import { useActiveRun } from "@/components/providers/workflow-run-provider"
import { useSession } from "@/components/providers/app-providers"
import { getProjectCosts, type LiveCostRun, type LiveUsageCost, type ProjectCostViewDto } from "@/lib/kosten-live"
import { aggregateLiveCost, groupExecutionsByRole, liveRunStatusView, splitExecutions, summarizePricing, unpricedBadgeLabel } from "@/lib/kosten-live-view"
import type { Role } from "@/lib/types"
import { cn } from "@/lib/utils"

export interface KostenScreenProps {
  // Kept for the page contract; permissions come from the authenticated backend.
  role?: Role
}

const ORANGE_BADGE_CLASSES = "border-status-partial/40 bg-status-partial/10 text-status-partial"
const GRAY_BADGE_CLASSES = "border-muted-foreground/30 bg-muted text-muted-foreground"

function money(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4, maximumFractionDigits: 6 }).format(value)
}

function chf(value: number): string {
  return new Intl.NumberFormat("de-CH", { style: "currency", currency: "CHF", minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(value)
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("de-CH", { dateStyle: "medium", timeStyle: "short" })
}

function duration(start: string, end?: string | null): string {
  if (!end) return "Läuft noch"
  const ms = new Date(end).getTime() - new Date(start).getTime()
  if (!Number.isFinite(ms) || ms < 0) return "—"
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds} s`
  return `${Math.floor(seconds / 60)} min ${seconds % 60} s`
}

function PricedAmount({ cost }: { cost: LiveUsageCost }) {
  return (
    <span className="font-semibold tabular-nums text-foreground">
      {money(cost.usd ?? 0)}
      {cost.chf_reference != null && <span className="mt-0.5 block text-xs font-normal text-muted-foreground">≈ {chf(cost.chf_reference)}</span>}
    </span>
  )
}

function RunStatus({ run }: { run: LiveCostRun }) {
  const view = liveRunStatusView(run.status, run.stop_reason)
  if (view.badge) return <RunStatusBadge status={view.badge} />
  return (
    <Badge variant="outline" className={cn("h-auto py-1", view.tone === "orange" ? ORANGE_BADGE_CLASSES : GRAY_BADGE_CLASSES)}>
      {view.label}
    </Badge>
  )
}

function RunCostSummary({ cost }: { cost: LiveUsageCost }) {
  if (cost.status === "priced" && cost.usd != null) return <PricedAmount cost={cost} />
  if (cost.status === "not_applicable") return <span className="text-sm text-muted-foreground">Keine externen KI-Kosten</span>
  return (
    <span className="flex flex-col items-end gap-1">
      <Badge variant="outline" className={cn("h-auto py-0.5", ORANGE_BADGE_CLASSES)}>Unvollständig bepreist</Badge>
      {cost.known_usd > 0 && <span className="text-xs text-muted-foreground">mind. {money(cost.known_usd)} bekannt</span>}
    </span>
  )
}

function CostTileValue({ total }: { total: LiveUsageCost }) {
  if (total.status === "priced" && total.usd != null) return <PricedAmount cost={total} />
  if (total.status === "not_applicable") return <span className="font-semibold tabular-nums">—</span>
  return (
    <div className="flex flex-col items-start gap-1.5">
      {total.known_usd > 0 ? (
        <span className="font-semibold tabular-nums">Mindestens {money(total.known_usd)}</span>
      ) : (
        <>
          <span className="font-semibold tabular-nums">—</span>
          <span className="text-xs font-normal text-muted-foreground">Noch nicht bepreisbar</span>
        </>
      )}
      <Badge variant="outline" className={cn("h-auto py-0.5", ORANGE_BADGE_CLASSES)}>{unpricedBadgeLabel(total.unpriced_call_count)}</Badge>
    </div>
  )
}

function costTileDetail(total: LiveUsageCost): string {
  if (total.status === "priced") return "Alle externen KI-Aufrufe sind vollständig bepreist."
  if (total.status === "not_applicable") return "Bisher sind keine externen KI-Kosten angefallen."
  return "Nur nachweislich bepreiste Aufrufe fliessen in die Summe ein."
}

function MetricCard({ label, value, detail, icon: Icon }: { label: string; value: React.ReactNode; detail: string; icon: React.ElementType }) {
  return (
    <article className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <Icon aria-hidden className="size-4 text-muted-foreground" />
      </div>
      <div className="mt-3 text-xl tracking-tight">{value}</div>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{detail}</p>
    </article>
  )
}

function RunCard({ run }: { run: LiveCostRun }) {
  const [open, setOpen] = React.useState(false)
  const { internalCount } = splitExecutions(run.executions)
  const roleGroups = groupExecutionsByRole(run.executions)
  return (
    <li className="rounded-xl border border-border bg-card shadow-sm">
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} className="flex w-full items-start gap-4 p-4 text-left outline-none transition-colors hover:bg-muted/25 focus-visible:ring-2 focus-visible:ring-ring">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h3 className="font-semibold text-foreground">Analyse-Durchlauf</h3>
            <RunStatus run={run} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{formatDate(run.started_at)} · gestartet von {run.user}</p>
        </div>
        <div className="shrink-0 text-right"><RunCostSummary cost={run.cost} /></div>
        <ChevronDown aria-hidden className={cn("mt-1 size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-border px-4 pb-4 pt-3">
          <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div><dt className="text-xs text-muted-foreground">Laufzeit</dt><dd className="mt-0.5 font-medium">{duration(run.started_at, run.ended_at)}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Tokens</dt><dd className="mt-0.5 font-medium tabular-nums">{run.input_tokens.toLocaleString("de-CH")} ein · {run.output_tokens.toLocaleString("de-CH")} aus</dd></div>
            <div><dt className="text-xs text-muted-foreground">Cache-Input</dt><dd className="mt-0.5 font-medium tabular-nums">{run.cached_input_tokens.toLocaleString("de-CH")}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Schutzlimit pro Lauf</dt><dd className="mt-0.5 font-medium">{run.max_cost_chf == null ? "Nicht festgelegt" : chf(run.max_cost_chf)}</dd></div>
          </dl>
          {run.web_calls > 0 && <p className="mt-3 text-xs text-muted-foreground">{run.web_calls} interne Werkzeug-Aufruf{run.web_calls === 1 ? "" : "e"} (Quellen- und Feldabrufe); keine externen KI-Kosten.</p>}
          <div className="mt-4 overflow-hidden rounded-lg border border-border">
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 bg-muted/30 px-3 py-2 text-xs font-medium text-muted-foreground"><span>Rolle</span><span>Kosten</span></div>
            {roleGroups.length === 0 ? <p className="px-3 py-4 text-sm text-muted-foreground">Keine externen KI-Aufrufe in diesem Durchlauf.</p> : roleGroups.map((group) => (
              <div key={group.key} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-t border-border px-3 py-3 text-sm">
                <div className="min-w-0"><p className="font-medium text-foreground">{group.roleLabel}</p><p className="mt-0.5 truncate text-xs text-muted-foreground">{group.models.length ? group.models.join(", ") : "Modell nicht bestätigt"} · {group.callCount} Aufruf{group.callCount === 1 ? "" : "e"} · {group.inputTokens.toLocaleString("de-CH")} / {group.outputTokens.toLocaleString("de-CH")} Tokens</p></div>
                <div className="text-right">{group.cost.status === "priced" && group.cost.usd != null ? <span className="font-medium tabular-nums text-foreground">{money(group.cost.usd)}</span> : <span aria-label="Kein Preis bekannt" className="text-muted-foreground">—</span>}</div>
              </div>
            ))}
          </div>
          {run.cost.unpriced_call_count > 0 && <p className="mt-2 text-xs text-muted-foreground">Für {run.cost.unpriced_call_count} Aufruf{run.cost.unpriced_call_count === 1 ? "" : "e"} lag zum Ausführungszeitpunkt noch keine Preisregel vor.</p>}
          {internalCount > 0 && <p className="mt-1 text-xs text-muted-foreground">{internalCount} interne{internalCount === 1 ? "r" : ""} Aufruf{internalCount === 1 ? "" : "e"} ohne externe KI-Kosten.</p>}
        </div>
      )}
    </li>
  )
}

export function KostenScreen(_: KostenScreenProps) {
  const { mode } = useSession()
  const { projectId, loading: projectLoading } = useActiveRun()
  const [data, setData] = React.useState<ProjectCostViewDto | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (mode !== "live" || !projectId) {
      setData(null)
      return
    }
    let active = true
    setError(null)
    getProjectCosts(projectId)
      .then((result) => { if (active) setData(result) })
      .catch(() => { if (active) setError("Die echten Kosten- und Laufzeitdaten konnten nicht geladen werden.") })
    return () => { active = false }
  }, [mode, projectId])

  const total = React.useMemo(() => aggregateLiveCost(data?.runs ?? []), [data])
  const summary = React.useMemo(() => summarizePricing(data?.runs ?? []), [data])
  const totalTokens = data?.runs.reduce((sum, run) => sum + run.input_tokens + run.output_tokens, 0) ?? 0
  const completedDurations = (data?.runs ?? []).map((run) => run.ended_at ? new Date(run.ended_at).getTime() - new Date(run.started_at).getTime() : null).filter((value): value is number => value != null && value >= 0)
  const averageDuration = completedDurations.length ? Math.round(completedDurations.reduce((sum, value) => sum + value, 0) / completedDurations.length / 1000) : null

  return (
    <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-8 px-4 py-7 pb-12 sm:px-6 lg:px-8" data-testid="kosten-screen">
      <header className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-[28px]">Kosten &amp; Laufzeit</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground sm:text-base">Echte Nutzung der KI-Dienste für dieses Projekt. Providerpreise werden in USD angezeigt; CHF dient nur als dokumentierte Orientierung.</p>
      </header>

      {mode !== "live" ? <div className="rounded-xl border border-dashed border-border bg-card px-6 py-10 text-center"><p className="font-medium text-foreground">Noch keine Live-Daten</p><p className="mt-1 text-sm text-muted-foreground">Kosten und Laufzeiten erscheinen nach dem ersten echten KI-Durchlauf.</p></div> : projectLoading ? <div className="h-44 animate-pulse rounded-xl border border-border bg-muted/40" /> : !projectId ? <div className="rounded-xl border border-dashed border-border bg-card px-6 py-10 text-center"><p className="font-medium text-foreground">Kein Projekt ausgewählt</p><p className="mt-1 text-sm text-muted-foreground">Wählen Sie zuerst ein Projekt aus.</p></div> : error ? <div role="alert" className="rounded-xl border border-destructive/35 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</div> : data && <>
        {summary.unpricedCallCount > 0 && (
          <div role="note" data-testid="pricing-notice" className="flex items-start gap-2.5 rounded-lg border border-status-partial/25 bg-status-partial/5 px-4 py-3 text-sm leading-relaxed text-foreground">
            <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-status-partial" />
            <p>Für {summary.unpricedCallCount} von {summary.externalCallCount} KI-Aufrufen lag zum Ausführungszeitpunkt noch keine veröffentlichte USD-Preisregel vor. Summen werden deshalb nicht als exakte Beträge ausgewiesen, sondern nur als belegte Mindestwerte.</p>
          </div>
        )}

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Kostenübersicht">
          <MetricCard label="Exakte KI-Kosten" value={<CostTileValue total={total} />} detail={costTileDetail(total)} icon={WalletCards} />
          <MetricCard label="KI-Aufrufe" value={<span className="font-semibold tabular-nums">{summary.externalCallCount}</span>} detail={data.runs.length === 1 ? "Externe KI-Aufrufe aus 1 Durchlauf" : `Externe KI-Aufrufe aus ${data.runs.length} Durchläufen`} icon={Layers3} />
          <MetricCard label="Tokens gesamt" value={<span className="font-semibold tabular-nums">{totalTokens.toLocaleString("de-CH")}</span>} detail="Ein- und Ausgabe-Tokens aus echten Providerantworten" icon={CircleDollarSign} />
          <MetricCard label="Ø Laufzeit" value={<span className="font-semibold tabular-nums">{averageDuration == null ? "—" : averageDuration < 60 ? `${averageDuration} s` : `${Math.floor(averageDuration / 60)} min ${averageDuration % 60} s`}</span>} detail="Abgeschlossene Durchläufe" icon={Clock3} />
        </section>

        <div className="flex flex-col gap-2">
          <p className="rounded-lg border border-border bg-muted/25 px-4 py-3 text-xs leading-relaxed text-muted-foreground">CHF-Orientierung: 1 USD = {data.chf_reference_rate.toFixed(4)} CHF, Referenz {data.chf_reference_as_of}.</p>
          {(data.web_research_calls ?? 0) > 0 && <p data-testid="firecrawl-note" className="rounded-lg border border-border bg-muted/25 px-4 py-3 text-xs leading-relaxed text-muted-foreground">Web-Recherche (Firecrawl): {data.web_research_calls} Aufruf{data.web_research_calls === 1 ? "" : "e"} — kreditbasiert, kein USD-Preis je Aufruf; nicht in den KI-Kosten enthalten.</p>}
        </div>

        <section aria-labelledby="history-heading"><div><h2 id="history-heading" className="text-lg font-semibold text-foreground">Durchlauf-Historie</h2><p className="mt-1 text-sm text-muted-foreground">Öffnen Sie einen Durchlauf für Tokens, tatsächliches Modell und Kosten je Aufruf.</p></div>{data.runs.length === 0 ? <div className="mt-4 rounded-xl border border-dashed border-border bg-card px-6 py-10 text-center"><p className="font-medium text-foreground">Noch keine Durchläufe</p><p className="mt-1 text-sm text-muted-foreground">Nach dem ersten KI-Durchlauf erscheinen hier die gemessenen Werte.</p></div> : <ul className="mt-4 flex flex-col gap-3">{data.runs.map((run) => <RunCard key={run.id} run={run} />)}</ul>}</section>
      </>}
    </div>
  )
}
