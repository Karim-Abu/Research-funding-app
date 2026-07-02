"use client"

import * as React from "react"
import {
  AlertTriangle,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  FileText,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import {
  RequirementSummaryBar,
  RequirementFilterBar,
  ReqBucketBadge,
} from "@/components/anforderungen/requirements-controls"
import {
  listRequirements,
  BASIS_LABELS,
  STALE_NOTICE,
  type RequirementAssessmentDto,
} from "@/lib/requirements"
import {
  REQ_FALLBACK,
  REQ_CATEGORY_ORDER,
  REQ_FILTER_ORDER,
  EVIDENCE_STATE_LABELS,
  HUMAN_STATE_LABELS,
  categorize,
  liveStatusToBucket,
  matchesFilter,
  summarize,
  type EvidenceState,
  type HumanState,
  type ReqBucket,
  type ReqFilter,
} from "@/lib/requirements-view"

// Normalized row the screen renders — derived purely in the frontend.
interface LiveRow {
  id: string
  requirementId: string
  title: string
  reasoning: string
  bucket: ReqBucket
  category: string
  evidenceState: EvidenceState
  humanState: HumanState
  openPoints: string[]
  basisLabel: string
  /** First linked anchor — target of the "Beleg ansehen" deep link. */
  firstAnchorId: string | null
}

function toRow(a: RequirementAssessmentDto): LiveRow {
  const bucket = liveStatusToBucket(a.status)
  const evidenceState: EvidenceState =
    a.evidence_links.length > 0 ? "present" : "missing"
  const firstAnchorId =
    a.evidence_links.find((l) => l.status === "active")?.anchor_id ??
    a.evidence_links[0]?.anchor_id ??
    null
  const humanState: HumanState =
    a.basis === "human_override"
      ? "confirmed"
      : bucket === "fulfilled"
        ? "not_required"
        : "needed"
  const openPoints = a.open_issues
    .map((i) => i.recommended_next_action || i.description)
    .filter((t): t is string => Boolean(t?.trim()))
  return {
    id: a.assessment_id,
    requirementId: a.requirement_id,
    title: a.title?.trim() || REQ_FALLBACK.title,
    reasoning: a.reasoning?.trim() || "Keine Begründung vorhanden.",
    bucket,
    category: categorize(a.requirement_id),
    evidenceState,
    humanState,
    openPoints,
    basisLabel: BASIS_LABELS[a.basis],
    firstAnchorId,
  }
}

export function LiveRequirements({ runId }: { runId: string }) {
  const [items, setItems] = React.useState<RequirementAssessmentDto[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [filter, setFilter] = React.useState<ReqFilter>("all")
  const [search, setSearch] = React.useState("")
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set())
  const [closedGroups, setClosedGroups] = React.useState<Set<string>>(new Set())
  const [techOpen, setTechOpen] = React.useState<Set<string>>(new Set())

  const load = React.useCallback(() => {
    setError(null)
    setItems(null)
    listRequirements(runId)
      .then(setItems)
      .catch((e) => setError(e instanceof Error ? e.message : "Fehler."))
  }, [runId])

  React.useEffect(() => load(), [load])

  function toggleSet(
    setter: React.Dispatch<React.SetStateAction<Set<string>>>,
    id: string
  ) {
    setter((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10 text-center">
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button variant="outline" className="mt-4" onClick={load}>
          <RefreshCw data-icon="inline-start" />
          Erneut versuchen
        </Button>
      </div>
    )
  }

  if (items === null) {
    return (
      <div className="mx-auto max-w-4xl space-y-3 px-6 py-10">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    )
  }

  const rows = items.map(toRow)
  const stale = items.some((a) => a.stale)
  const summary = summarize(rows)

  // Filter chips: only offer conditions that actually occur.
  const availableFilters = REQ_FILTER_ORDER.filter((f) => {
    if (f === "all") return false
    return rows.some((r) => matchesFilter(r, f))
  })

  const query = search.trim().toLowerCase()
  const visible = rows.filter((r) => {
    if (!matchesFilter(r, filter)) return false
    if (query && !`${r.title} ${r.reasoning}`.toLowerCase().includes(query))
      return false
    return true
  })

  const groups = REQ_CATEGORY_ORDER.map((category) => ({
    category,
    rows: visible.filter((r) => r.category === category),
  })).filter((g) => g.rows.length > 0)

  const firstBlocker = rows.find((r) => r.bucket === "blocked")
  const hasBlockers = Boolean(firstBlocker)
  const openTotal = summary.open + summary.partial + summary.blocked

  function jumpToFirstBlocker() {
    if (!firstBlocker) return
    setClosedGroups((prev) => {
      const next = new Set(prev)
      next.delete(firstBlocker!.category)
      return next
    })
    setExpanded((prev) => new Set(prev).add(firstBlocker!.id))
    requestAnimationFrame(() => {
      document
        .getElementById(`req-${firstBlocker!.id}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" })
    })
  }

  return (
    <div className="flex min-h-full flex-col">
      <div className="flex-1 px-6 py-8 pb-32">
        <div className="mx-auto flex max-w-4xl flex-col gap-6">
          {/* Header */}
          <div className="flex flex-col gap-1">
            <h1 className="text-balance text-2xl font-semibold text-foreground">
              Anforderungen &amp; Fördervoraussetzungen
            </h1>
            <p className="text-sm text-muted-foreground">
              Automatisch erkannte Voraussetzungen, Belege und offene Prüfpunkte
              für diesen Antrag.
            </p>
          </div>

          {stale && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{STALE_NOTICE}</span>
            </div>
          )}

          {rows.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-muted/20 px-6 py-16 text-center">
              <p className="text-sm text-muted-foreground">
                Es wurden noch keine Anforderungen erkannt.
              </p>
            </div>
          ) : (
            <>
              <RequirementSummaryBar summary={summary} />

              <RequirementFilterBar
                available={availableFilters}
                value={filter}
                onChange={setFilter}
                search={search}
                onSearchChange={setSearch}
              />

              {groups.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  Keine Anforderungen entsprechen dem aktuellen Filter.
                </p>
              ) : (
                <div className="flex flex-col gap-4">
                  {groups.map(({ category, rows: groupRows }) => {
                    const open = !closedGroups.has(category)
                    const fulfilled = groupRows.filter(
                      (r) => r.bucket === "fulfilled"
                    ).length
                    return (
                      <section
                        key={category}
                        className="overflow-hidden rounded-lg border border-border bg-card"
                      >
                        <button
                          type="button"
                          onClick={() => toggleSet(setClosedGroups, category)}
                          aria-expanded={open}
                          className="flex w-full items-center gap-3 border-b border-border bg-muted/30 px-5 py-3.5 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                        >
                          {open ? (
                            <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
                          )}
                          <h2 className="flex-1 text-sm font-semibold text-foreground">
                            {category}
                          </h2>
                          <span className="text-xs text-muted-foreground">
                            {fulfilled} / {groupRows.length} erfüllt
                          </span>
                        </button>

                        {open && (
                          <div>
                            {groupRows.map((row) => (
                              <LiveRequirementRow
                                key={row.id}
                                row={row}
                                expanded={expanded.has(row.id)}
                                techOpen={techOpen.has(row.id)}
                                onToggle={() => toggleSet(setExpanded, row.id)}
                                onToggleTech={() => toggleSet(setTechOpen, row.id)}
                              />
                            ))}
                          </div>
                        )}
                      </section>
                    )
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Sticky footer — blocker-aware next step */}
      {rows.length > 0 && (
        <footer className="sticky bottom-0 z-10 border-t border-border bg-background/95 backdrop-blur-sm">
          <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-6 py-4">
            <p className="text-sm text-muted-foreground">
              {hasBlockers ? (
                <>
                  <span className="font-medium text-destructive">
                    {summary.blocked} Blocker
                  </span>{" "}
                  {summary.blocked === 1 ? "verhindert" : "verhindern"} aktuell den
                  nächsten Schritt.
                </>
              ) : (
                <>
                  <span className="font-medium text-foreground">
                    {openTotal} offene{openTotal === 1 ? "r Punkt" : " Punkte"}
                  </span>{" "}
                  {openTotal === 1 ? "wird" : "werden"} ins Review übernommen.
                </>
              )}
            </p>
            <div className="flex items-center gap-2">
              {hasBlockers ? (
                <>
                  <Button variant="outline" onClick={jumpToFirstBlocker}>
                    Zum ersten Blocker springen
                  </Button>
                  <Button disabled>Blocker zuerst klären</Button>
                </>
              ) : (
                <Button render={<a href="/editor" />} nativeButton={false}>
                  Weiter zum Entwurf
                </Button>
              )}
            </div>
          </div>
        </footer>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------
function LiveRequirementRow({
  row,
  expanded,
  techOpen,
  onToggle,
  onToggleTech,
}: {
  row: LiveRow
  expanded: boolean
  techOpen: boolean
  onToggle: () => void
  onToggleTech: () => void
}) {
  return (
    <div id={`req-${row.id}`} className="border-b border-border last:border-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors min-h-[44px] hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        {expanded ? (
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        )}
        <ReqBucketBadge bucket={row.bucket} />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-sm font-medium text-foreground">{row.title}</span>
          <span className="truncate text-xs text-muted-foreground">
            {row.reasoning}
          </span>
        </div>
        {row.evidenceState === "missing" && (
          <span className="shrink-0 rounded-full bg-status-partial/10 px-2 py-0.5 text-xs text-status-partial">
            Ohne Beleg
          </span>
        )}
        {row.humanState === "needed" && (
          <span className="hidden shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground sm:inline">
            Prüfung nötig
          </span>
        )}
      </button>

      {expanded && (
        <div className="flex flex-col gap-4 border-t border-border bg-muted/20 px-5 pb-5 pt-4">
          <p className="text-sm leading-relaxed text-foreground">{row.reasoning}</p>

          {/* Status row: evidence + human review */}
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1 text-xs text-foreground">
              <FileText className="size-3.5 text-muted-foreground" />
              {row.evidenceState === "missing"
                ? REQ_FALLBACK.evidence
                : EVIDENCE_STATE_LABELS[row.evidenceState]}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1 text-xs text-foreground">
              <CheckCircle2 className="size-3.5 text-muted-foreground" />
              {row.humanState === "needed"
                ? REQ_FALLBACK.human
                : HUMAN_STATE_LABELS[row.humanState]}
            </span>
          </div>

          {/* Open points */}
          {row.openPoints.length > 0 && (
            <div className="flex flex-col gap-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Offene Punkte
              </p>
              <ul className="flex flex-col gap-1">
                {row.openPoints.map((point) => (
                  <li key={point} className="text-sm text-foreground">
                    • {point}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Portal field — no portal mapping in the contract yet */}
          <p className="text-xs text-muted-foreground">
            Betroffenes Portal-Feld: {REQ_FALLBACK.portal}
          </p>

          {/* Actions — guidance links only; confirmation/decisions live in the
              Review (no write-back from this screen). */}
          <div className="flex flex-wrap items-center gap-2">
            {row.evidenceState === "present" && row.firstAnchorId ? (
              <Button
                variant="outline"
                size="sm"
                render={
                  <a
                    href={`/quellen?tab=evidenz&anchor=${encodeURIComponent(row.firstAnchorId)}`}
                  />
                }
                nativeButton={false}
              >
                Beleg ansehen
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                render={<a href="/quellen" />}
                nativeButton={false}
              >
                Quelle ergänzen
              </Button>
            )}
            <Button variant="outline" size="sm" render={<a href="/review" />} nativeButton={false}>
              In Review übernehmen
            </Button>
            {row.humanState === "needed" && (
              <Button variant="ghost" size="sm" render={<a href="/review" />} nativeButton={false}>
                Kommentar im Review erfassen
              </Button>
            )}
            <span className="text-xs text-muted-foreground">
              Bestätigung und Korrektur erfolgen im Review.
            </span>
          </div>

          {/* Technical details — collapsed, never in the standard view */}
          <div>
            <button
              type="button"
              onClick={onToggleTech}
              aria-expanded={techOpen}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              {techOpen ? (
                <ChevronDown className="h-3.5 w-3.5" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5" />
              )}
              Technische Details
            </button>
            {techOpen && (
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <dt>Anforderungs-ID</dt>
                <dd className="font-mono break-all">{row.requirementId}</dd>
                <dt>Grundlage</dt>
                <dd>{row.basisLabel}</dd>
              </dl>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
