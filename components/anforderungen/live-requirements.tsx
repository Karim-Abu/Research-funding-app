"use client"

import * as React from "react"
import {
  AlertTriangle,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  ExternalLink,
  FileText,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { CanonicalStatusBadge } from "@/components/status/canonical-status"
import { NextActionsCard } from "@/components/review/fix-queue"
import { useFixQueue } from "@/lib/fix-queue"
import {
  RequirementSummaryBar,
  RequirementFilterBar,
  ReqBucketBadge,
} from "@/components/anforderungen/requirements-controls"
import {
  listRequirements,
  STALE_NOTICE,
  STATUS_LABELS,
  STATUS_REASONS,
  type RequirementAssessmentDto,
  type RequirementStatus,
  type RuleEvidenceDto,
} from "@/lib/requirements"
import {
  REQ_FALLBACK,
  REQ_CATEGORY_ORDER,
  REQ_FILTER_ORDER,
  REQ_NEUTRAL_ACTION,
  EVIDENCE_STATE_LABELS,
  HUMAN_STATE_LABELS,
  categorize,
  liveStatusToBucket,
  matchesFilter,
  primaryActionFor,
  relevanceFor,
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
  /** Präziser Backend-Status — Detailebene rendert das 5er-Statuslabel. */
  status: RequirementStatus
  bucket: ReqBucket
  category: string
  evidenceState: EvidenceState
  humanState: HumanState
  /** RUN 2A Slice 1: Guidance-Hinweise laufen in eine getrennte Sektion und
   *  zählen in keiner Quote, keinem Filter und keiner Gruppe. */
  displayMode: "requirement" | "guidance"
  openPoints: string[]
  /** First linked anchor — target of the "Beleg ansehen" deep link. */
  firstAnchorId: string | null
  ruleEvidence: RuleEvidenceDto[]
}

function toRow(a: RequirementAssessmentDto): LiveRow {
  const bucket = liveStatusToBucket(a.status)
  const evidenceState: EvidenceState =
    a.evidence_links.length > 0 ? "present" : "missing"
  const firstAnchorId =
    a.evidence_links.find((l) => l.status === "active")?.anchor_id ??
    a.evidence_links[0]?.anchor_id ??
    null
  // RUN 2A Slice 1: die Review-Dimension kommt aus dem Contract
  // (review_status) — ein erfüllter Hybrid-Check bleibt «Erfüllt» und zeigt
  // die offene Bestätigung als Sekundärinformation, nie als Herabstufung.
  const humanState: HumanState =
    a.basis === "human_override" || a.review_status === "confirmed"
      ? "confirmed"
      : a.review_status === "required"
        ? "needed"
        : a.review_status === "not_required" || bucket === "fulfilled"
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
    status: a.status,
    bucket,
    category: categorize(a.requirement_id),
    evidenceState,
    humanState,
    displayMode: a.display_mode === "guidance" ? "guidance" : "requirement",
    openPoints,
    firstAnchorId,
    ruleEvidence: a.rule_evidence ?? [],
  }
}

export function LiveRequirements({
  runId,
  focusRequirementId,
}: {
  runId: string
  /** Deep link (?requirement=…): expand, scroll to and highlight this row. */
  focusRequirementId?: string | null
}) {
  const [items, setItems] = React.useState<RequirementAssessmentDto[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [filter, setFilter] = React.useState<ReqFilter>("all")
  const [search, setSearch] = React.useState("")
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set())
  const [closedGroups, setClosedGroups] = React.useState<Set<string>>(new Set())
  const focusHandledRef = React.useRef(false)

  const load = React.useCallback(() => {
    setError(null)
    setItems(null)
    listRequirements(runId)
      .then(setItems)
      .catch((e) => setError(e instanceof Error ? e.message : "Fehler."))
  }, [runId])

  React.useEffect(() => load(), [load])

  // R2.5 — kompakte «Nächste Aufgaben» (Fix Queue); bei Fehler/leer erscheint
  // der Block nicht (alte Darstellung bleibt vollständig erhalten).
  const { queue: fixQueue } = useFixQueue(runId)

  // Deep link: once the data is there, expand the targeted row (matched by
  // requirement_id or assessment_id), scroll to it and highlight it briefly.
  React.useEffect(() => {
    if (!focusRequirementId || focusHandledRef.current || !items) return
    const match = items.find(
      (a) =>
        a.requirement_id === focusRequirementId ||
        a.assessment_id === focusRequirementId
    )
    if (!match) return
    focusHandledRef.current = true
    setExpanded((prev) => new Set(prev).add(match.assessment_id))
    requestAnimationFrame(() => {
      const el = document.getElementById(`req-${match.assessment_id}`)
      el?.scrollIntoView({ behavior: "smooth", block: "center" })
      el?.classList.add("deeplink-highlight")
      setTimeout(() => el?.classList.remove("deeplink-highlight"), 2200)
    })
  }, [focusRequirementId, items])

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

  const allRows = items.map(toRow)
  // Guidance zählt nirgends mit: eigene Sektion, keine Quote, kein Filter.
  const guidanceRows = allRows.filter((r) => r.displayMode === "guidance")
  const rows = allRows.filter((r) => r.displayMode === "requirement")
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
            {/* h2: Seiten-h1 ist «Analyse & Recherche» (app/anforderungen). */}
            <h2 className="text-balance text-xl font-semibold text-foreground">
              Anforderungen &amp; Fördervoraussetzungen
            </h2>
            <p className="text-sm text-muted-foreground">
              Automatisch erkannte Voraussetzungen, Belege und offene Prüfpunkte
              für diesen Antrag.
            </p>
            {/* R1.3 — kanonischer Gesamtstatus (eine Quelle für alle Screens). */}
            <div className="mt-1">
              <CanonicalStatusBadge runId={runId} />
            </div>
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

          {/* R2.5 — priorisierte «Nächste Aufgaben» aus der Fix Queue. */}
          {fixQueue !== null && fixQueue.next_actions.length > 0 && (
            <NextActionsCard groups={fixQueue.next_actions} limit={5} />
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
                                onToggle={() => toggleSet(setExpanded, row.id)}
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

          {/* RUN 2A Slice 1: Guidance-Hinweise (Registry severity=info) —
              reine Information, getrennt von den zählenden Anforderungen. */}
          {guidanceRows.length > 0 && (
            <section
              className="rounded-lg border border-border bg-muted/20 px-5 py-4"
              data-testid="guidance-notes"
            >
              <h2 className="text-sm font-semibold text-foreground">Hinweise</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Informationen ohne Erfüllungspflicht — sie zählen in keiner
                Quote und blockieren nichts.
              </p>
              <ul className="mt-2 flex flex-col gap-1.5">
                {guidanceRows.map((row) => (
                  <li key={row.id} className="text-sm text-foreground">
                    <span className="font-medium">{row.title}</span>
                    <span className="text-muted-foreground">
                      {" "}
                      — {row.reasoning}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
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
                  {/* Präzise Teilmengen-Formulierung: blockierende Anforderungen,
                      nicht die kanonische Gesamt-Blockerzahl (siehe Badge oben). */}
                  <span className="font-medium text-destructive">
                    {summary.blocked} blockierende{" "}
                    {summary.blocked === 1 ? "Anforderung" : "Anforderungen"}
                  </span>{" "}
                  {summary.blocked === 1 ? "verhindert" : "verhindern"} aktuell den
                  nächsten Schritt.
                </>
              ) : (
                <>
                  <span className="font-medium text-foreground">
                    {openTotal} offene{openTotal === 1 ? "r Punkt" : " Punkte"}
                  </span>{" "}
                  {openTotal === 1 ? "erscheint" : "erscheinen"} automatisch in der Qualitätsprüfung.
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
  onToggle,
}: {
  row: LiveRow
  expanded: boolean
  onToggle: () => void
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
            {row.bucket === "fulfilled"
              ? "Maschinell geprüft · Bestätigung offen"
              : "Prüfung nötig"}
          </span>
        )}
      </button>

      {expanded && (
        <div className="flex flex-col gap-4 border-t border-border bg-muted/20 px-5 pb-5 pt-4">
          {/* Präziser fachlicher Status mit Kurzbegründung (RUN 4A). */}
          <p className="text-sm text-foreground">
            <span className="font-medium">{STATUS_LABELS[row.status]}</span>
            <span className="text-muted-foreground">
              {" "}
              — {STATUS_REASONS[row.status]}
            </span>
          </p>

          {/* System finding — clearly separated from the human decision. */}
          <div className="flex flex-col gap-1">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Systembefund
            </p>
            <p className="text-sm leading-relaxed text-foreground">{row.reasoning}</p>
          </div>

          <p className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Warum relevant?</span>{" "}
            {relevanceFor(row.category)}
          </p>

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

          {row.ruleEvidence.length > 0 && (
            <div className="flex flex-col gap-2" data-testid="rule-evidence">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Regelgrundlage
              </p>
              {row.ruleEvidence.map((evidence) => (
                <div
                  key={`${evidence.rule_id}:${evidence.source_ref}`}
                  className="rounded-md border border-border bg-card px-3 py-2"
                >
                  <p className="text-xs font-medium text-foreground">
                    {evidence.evidence_label}
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-foreground">
                    {evidence.evidence_quote}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Quelle: {evidence.source_title} · Registry{" "}
                    {evidence.registry_version}
                    {evidence.last_verified
                      ? ` · geprüft ${evidence.last_verified}`
                      : ""}
                  </p>
                  {/* RUN 4A: direkter Absprung zur offiziellen Regelquelle —
                      nur wenn die Registry eine URL führt. */}
                  {evidence.source_url && (
                    <a
                      href={evidence.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-1.5 inline-flex items-center gap-1 rounded text-xs font-medium text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <ExternalLink className="size-3.5" aria-hidden />
                      Offizielle Regel öffnen
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Portal field — no portal mapping in the contract yet.
              TODO(contract): map requirements onto portal fields once the
              backend exposes the relationship. */}
          <p className="text-xs text-muted-foreground">{REQ_FALLBACK.portal}.</p>

          {/* Actions — one primary CTA per problem type; guidance links only.
              Confirmation/decisions live in the Qualitätsprüfung (no
              write-back from this screen). */}
          <LiveRowActions row={row} />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Row actions — exactly one primary CTA, secondaries stay quiet (ghost).
// ---------------------------------------------------------------------------
function LiveRowActions({ row }: { row: LiveRow }) {
  const primary = primaryActionFor(row)
  const evidenceHref = row.firstAnchorId
    ? `/anforderungen?tab=evidenz&anchor=${encodeURIComponent(row.firstAnchorId)}`
    : null

  // Secondaries: evidence link + neutral review link, unless the primary
  // already covers them.
  const secondaries: { label: string; href: string }[] = []
  if (evidenceHref && primary?.href !== evidenceHref) {
    secondaries.push({ label: "Beleg ansehen", href: evidenceHref })
  }
  if (primary?.href !== REQ_NEUTRAL_ACTION.href) {
    secondaries.push(REQ_NEUTRAL_ACTION)
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {primary && (
        <Button size="sm" render={<a href={primary.href} />} nativeButton={false}>
          {primary.label}
        </Button>
      )}
      {secondaries.map((action) => (
        <Button
          key={action.label}
          variant="ghost"
          size="sm"
          render={<a href={action.href} />}
          nativeButton={false}
        >
          {action.label}
        </Button>
      ))}
      <span className="text-xs text-muted-foreground">
        Befunde erscheinen automatisch in der Qualitätsprüfung. Bestätigung und
        Korrektur erfolgen dort.
      </span>
    </div>
  )
}
