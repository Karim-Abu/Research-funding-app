"use client"

import * as React from "react"
import { Check, ChevronRight, Minus, RotateCcw, Search } from "lucide-react"
import { RunDetailDrawer } from "@/components/kosten/run-detail-drawer"
import { RunStatusBadge } from "@/components/kosten/run-status-badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  RUN_STATUS_LABELS,
  RUN_TYPE_LABELS,
  filterAndSortRuns,
  formatCost,
  formatDateTime,
  formatDuration,
  getRunDurationMs,
  parseProviderModelKey,
  runProviderModelKeys,
  runProviderModelLabel,
  type KostenRunStatus,
  type KostenRunType,
  type KostenRunViewModel,
  type RunFilters,
  type RunSort,
} from "@/lib/kosten"
import { cn } from "@/lib/utils"

const DEFAULT_FILTERS: RunFilters = {
  query: "",
  status: "all",
  type: "all",
  providerModel: "all",
  sort: "date_desc",
}

function AvailabilityMark({ enabled, label }: { enabled: boolean; label: string }) {
  return enabled ? (
    <span className="inline-flex items-center gap-1 text-status-fulfilled">
      <Check aria-hidden className="size-4" />
      <span className="sr-only">{label}: aktiv</span>
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-muted-foreground">
      <Minus aria-hidden className="size-4" />
      <span className="sr-only">{label}: nicht aktiv</span>
    </span>
  )
}

function hasActiveFilters(filters: RunFilters): boolean {
  return (
    filters.query !== "" ||
    filters.status !== "all" ||
    filters.type !== "all" ||
    filters.providerModel !== "all" ||
    filters.sort !== "date_desc"
  )
}

export function RunsTable({ runs }: { runs: readonly KostenRunViewModel[] }) {
  const [filters, setFilters] = React.useState<RunFilters>(DEFAULT_FILTERS)
  const [selectedRun, setSelectedRun] = React.useState<KostenRunViewModel | null>(null)
  const [drawerOpen, setDrawerOpen] = React.useState(false)

  const visibleRuns = React.useMemo(
    () => filterAndSortRuns(runs, filters),
    [runs, filters]
  )
  const providerOptions = React.useMemo(() => {
    const keys = new Set<string>()
    for (const run of runs) {
      for (const key of runProviderModelKeys(run)) keys.add(key)
    }
    return [...keys]
      .map((key) => ({ key, ...parseProviderModelKey(key) }))
      .sort(
        (left, right) =>
          left.provider.localeCompare(right.provider, "de-CH") ||
          left.model.localeCompare(right.model, "de-CH")
      )
  }, [runs])

  const webCount = visibleRuns.filter((run) => run.webEnabled).length
  const stoppedCount = visibleRuns.filter(
    (run) => run.status === "stopped_cost"
  ).length

  function openRun(run: KostenRunViewModel) {
    setSelectedRun(run)
    setDrawerOpen(true)
  }

  function updateFilters(next: Partial<RunFilters>) {
    setFilters((current) => ({ ...current, ...next }))
  }

  return (
    <section aria-labelledby="runs-heading">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="runs-heading" className="text-lg font-semibold text-foreground">
            Durchlauf-Historie
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Kosten, Laufzeit und technischer Status der bisherigen Durchläufe.
          </p>
        </div>
      </div>

      {runs.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-border bg-card px-6 py-10 text-center">
          <p className="text-sm font-medium text-foreground">Noch keine Durchläufe</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Kosten- und Laufzeitdaten erscheinen nach dem ersten gestarteten Lauf.
          </p>
        </div>
      ) : (
        <>
          <div
            role="group"
            aria-label="Durchläufe filtern und sortieren"
            className="mt-4 rounded-lg border border-border bg-card p-3"
          >
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-[minmax(230px,1.5fr)_repeat(4,minmax(150px,1fr))_auto]">
              <div className="relative sm:col-span-2 xl:col-span-1">
                <Label htmlFor="run-search" className="sr-only">
                  Nach Nutzer:in oder Audit-Referenz suchen
                </Label>
                <Search
                  aria-hidden
                  className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                />
                <Input
                  id="run-search"
                  value={filters.query}
                  onChange={(event) => updateFilters({ query: event.target.value })}
                  placeholder="Nutzer:in oder Audit-Referenz"
                  className="pl-9"
                />
              </div>

              <Select
                value={filters.status}
                onValueChange={(value) =>
                  updateFilters({ status: (value ?? "all") as KostenRunStatus | "all" })
                }
              >
                <SelectTrigger className="h-9 w-full" aria-label="Status filtern">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Alle Status</SelectItem>
                  {Object.entries(RUN_STATUS_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                value={filters.type}
                onValueChange={(value) =>
                  updateFilters({ type: (value ?? "all") as KostenRunType | "all" })
                }
              >
                <SelectTrigger className="h-9 w-full" aria-label="Art filtern">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Alle Arten</SelectItem>
                  {Object.entries(RUN_TYPE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                value={filters.providerModel}
                onValueChange={(value) =>
                  updateFilters({ providerModel: value ?? "all" })
                }
              >
                <SelectTrigger className="h-9 w-full" aria-label="Provider oder Modell filtern">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Alle Provider / Modelle</SelectItem>
                  {providerOptions.map((option) => (
                    <SelectItem key={option.key} value={option.key}>
                      {option.provider} / {option.model}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                value={filters.sort}
                onValueChange={(value) =>
                  updateFilters({ sort: (value ?? "date_desc") as RunSort })
                }
              >
                <SelectTrigger className="h-9 w-full" aria-label="Durchläufe sortieren">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="date_desc">Neueste zuerst</SelectItem>
                  <SelectItem value="cost_desc">Höchste Kosten</SelectItem>
                  <SelectItem value="duration_desc">Längste Laufzeit</SelectItem>
                </SelectContent>
              </Select>

              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={!hasActiveFilters(filters)}
                onClick={() => setFilters(DEFAULT_FILTERS)}
                className="h-9 justify-center"
              >
                <RotateCcw aria-hidden className="size-4" />
                Zurücksetzen
              </Button>
            </div>
            <p className="mt-3 text-xs text-muted-foreground" aria-live="polite">
              {visibleRuns.length} {visibleRuns.length === 1 ? "Durchlauf" : "Durchläufe"}
              <span aria-hidden> · </span>
              {webCount} mit Webrecherche
              <span aria-hidden> · </span>
              {stoppedCount} durch Kostenlimit gestoppt
            </p>
          </div>

          {visibleRuns.length === 0 ? (
            <div className="mt-4 rounded-lg border border-dashed border-border bg-card px-6 py-10 text-center">
              <p className="text-sm font-medium text-foreground">
                Keine passenden Durchläufe
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Passen Sie die Filter an oder setzen Sie sie zurück.
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-4"
                onClick={() => setFilters(DEFAULT_FILTERS)}
              >
                Filter zurücksetzen
              </Button>
            </div>
          ) : (
            <>
              <div className="mt-4 hidden overflow-x-auto rounded-lg border border-border bg-card xl:block">
                <table className="w-full min-w-[1060px] text-sm" aria-label="Durchlauf-Historie">
                  <thead>
                    <tr className="border-b border-border bg-muted/25 text-left text-xs text-muted-foreground">
                      <th scope="col" className="px-3 py-3 font-medium">Datum</th>
                      <th scope="col" className="px-3 py-3 font-medium">Art</th>
                      <th scope="col" className="px-3 py-3 font-medium">Nutzer:in</th>
                      <th scope="col" className="px-3 py-3 font-medium">Modell / Provider</th>
                      <th scope="col" className="px-3 py-3 text-center font-medium">KI</th>
                      <th scope="col" className="px-3 py-3 text-center font-medium">Web</th>
                      <th scope="col" className="px-3 py-3 text-right font-medium">Laufzeit</th>
                      <th scope="col" className="px-3 py-3 text-right font-medium">Kosten</th>
                      <th scope="col" className="px-3 py-3 font-medium">Status</th>
                      <th scope="col" className="w-10 px-3 py-3"><span className="sr-only">Details</span></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {visibleRuns.map((run) => (
                      <tr
                        key={run.id}
                        tabIndex={0}
                        onClick={() => openRun(run)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault()
                            openRun(run)
                          }
                        }}
                        aria-label={`Details zu ${RUN_TYPE_LABELS[run.type]} vom ${formatDateTime(run.startedAt)} öffnen`}
                        className={cn(
                          "min-h-11 cursor-pointer transition-colors hover:bg-accent/40",
                          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                        )}
                      >
                        <td className="whitespace-nowrap px-3 py-3 text-xs text-foreground">{formatDateTime(run.startedAt)}</td>
                        <td className="px-3 py-3 text-foreground">{RUN_TYPE_LABELS[run.type]}</td>
                        <td className="px-3 py-3 text-muted-foreground">{run.user}</td>
                        <td className="max-w-56 px-3 py-3 text-foreground">{runProviderModelLabel(run)}</td>
                        <td className="px-3 py-3 text-center"><AvailabilityMark enabled={run.kiEnabled} label="KI" /></td>
                        <td className="px-3 py-3 text-center"><AvailabilityMark enabled={run.webEnabled} label="Webrecherche" /></td>
                        <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{formatDuration(getRunDurationMs(run))}</td>
                        <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{formatCost(run.cost)}</td>
                        <td className="px-3 py-3"><RunStatusBadge status={run.status} /></td>
                        <td className="px-3 py-3 text-right"><ChevronRight aria-hidden className="size-4 text-muted-foreground" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <ul className="mt-4 flex flex-col gap-3 xl:hidden">
                {visibleRuns.map((run) => (
                  <li key={run.id}>
                    <button
                      type="button"
                      onClick={() => openRun(run)}
                      aria-label={`Details zu ${RUN_TYPE_LABELS[run.type]} vom ${formatDateTime(run.startedAt)} öffnen`}
                      className="w-full rounded-lg border border-border bg-card p-4 text-left outline-none transition-colors hover:bg-accent/30 focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-medium text-foreground">{RUN_TYPE_LABELS[run.type]}</p>
                          <p className="mt-0.5 text-xs text-muted-foreground">{formatDateTime(run.startedAt)} · {run.user}</p>
                        </div>
                        <ChevronRight aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                      </div>
                      <p className="mt-3 text-sm text-foreground">{runProviderModelLabel(run)}</p>
                      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <span className="block text-xs text-muted-foreground">Laufzeit</span>
                          <span className="font-medium tabular-nums">{formatDuration(getRunDurationMs(run))}</span>
                        </div>
                        <div>
                          <span className="block text-xs text-muted-foreground">Kosten</span>
                          <span className="font-medium tabular-nums">{formatCost(run.cost)}</span>
                        </div>
                      </div>
                      <RunStatusBadge status={run.status} className="mt-3" />
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}

      <RunDetailDrawer run={selectedRun} open={drawerOpen} onOpenChange={setDrawerOpen} />
    </section>
  )
}
