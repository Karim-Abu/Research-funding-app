"use client"

import * as React from "react"
import {
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  RefreshCw,
  CheckCheck,
  PenLine,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { MachineStatusBadge } from "@/components/status/machine-status-badge"
import { HumanCheckMark } from "@/components/status/human-check-mark"
import { EvidenceDrawer } from "@/components/quellen/evidence-drawer"
import { cn } from "@/lib/utils"
import {
  RequirementSummaryBar,
  RequirementFilterBar,
} from "@/components/anforderungen/requirements-controls"
import {
  requirements as initialRequirements,
  GROUPS,
  runState,
} from "@/lib/anforderungen-mock-data"
import { dummyEvidence } from "@/lib/quellen-mock-data"
import type { Requirement, RequirementGroup } from "@/lib/anforderungen-mock-data"
import { REQUIREMENT_STATUS_LABELS, type MachineStatus } from "@/lib/types"
import {
  machineStatusToBucket,
  matchesFilter,
  summarize,
  REQ_FILTER_ORDER,
  type EvidenceState,
  type HumanState,
  type ReqBucket,
  type ReqFilter,
  type ReqView,
} from "@/lib/requirements-view"
import type { EvidenceCard } from "@/lib/quellen-mock-data"

// Effective status of a mock row: override wins, otherwise a missing evidence
// chip forces "open" (matches the row rendering below).
function effectiveBucket(r: Requirement): ReqBucket {
  const ms: MachineStatus = r.override
    ? r.override.newStatus
    : !r.evidence
      ? "open"
      : r.machineStatus
  return machineStatusToBucket(ms)
}

function rowView(r: Requirement): ReqView {
  const bucket = effectiveBucket(r)
  const evidenceState: EvidenceState = r.evidence ? "present" : "missing"
  const humanState: HumanState = r.humanCheck
    ? "confirmed"
    : bucket === "fulfilled"
      ? "not_required"
      : "needed"
  return { bucket, evidenceState, humanState }
}

// ---------------------------------------------------------------------------
// Page-level state types
// ---------------------------------------------------------------------------

type PageState = "default" | "loading" | "empty" | "stopped"

// Set to true only during internal prototyping — never in the evaluation view.
const SHOW_DEBUG_CONTROLS = false

// ---------------------------------------------------------------------------
// Stopped run banner
// ---------------------------------------------------------------------------

function StoppedRunBanner({ stoppedAt }: { stoppedAt: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-status-partial/40 bg-status-partial/8 px-4 py-3">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-status-partial" />
      <div className="flex flex-1 flex-col gap-1">
        <p className="text-sm font-medium text-foreground">
          Durchlauf gestoppt: Kostenlimit erreicht. Bisherige Ergebnisse sind gespeichert.
        </p>
        <p className="text-xs text-muted-foreground">Stand: unvollständiger Durchlauf · {stoppedAt}</p>
      </div>
      <Button size="sm" variant="outline" className="shrink-0">
        <RefreshCw className="mr-1.5 size-3.5" />
        Analyse fortsetzen
      </Button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Override dialog
// ---------------------------------------------------------------------------

interface OverrideDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  rowTitle: string
  onConfirm: (newStatus: MachineStatus, comment: string) => void
}

function OverrideDialog({ open, onOpenChange, rowTitle, onConfirm }: OverrideDialogProps) {
  const [status, setStatus] = React.useState<MachineStatus>("partial")
  const [comment, setComment] = React.useState("")
  const [saving, setSaving] = React.useState(false)

  // Reset on open
  React.useEffect(() => {
    if (open) { setStatus("partial"); setComment(""); setSaving(false) }
  }, [open])

  function handleConfirm() {
    if (!comment.trim()) return
    setSaving(true)
    setTimeout(() => {
      setSaving(false)
      onConfirm(status, comment)
      onOpenChange(false)
    }, 500)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="text-base">Bewertung korrigieren</DialogTitle>
          <p className="text-sm text-muted-foreground">{rowTitle}</p>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="override-status" className="text-sm font-medium">
              Neuer Status
            </Label>
            <Select value={status} onValueChange={(v) => setStatus(v as MachineStatus)}>
              <SelectTrigger id="override-status" className="w-full">
                <span>{REQUIREMENT_STATUS_LABELS[status]}</span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="verified">Erfüllt</SelectItem>
                <SelectItem value="partial">Teilweise erfüllt</SelectItem>
                <SelectItem value="open">Offen</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="override-comment" className="text-sm font-medium">
              Begründung
              <span className="ml-1 font-normal text-muted-foreground">(Pflichtfeld)</span>
            </Label>
            <Textarea
              id="override-comment"
              placeholder="Grund für die Korrektur…"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              className="resize-none text-sm"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Abbrechen
          </Button>
          <Button onClick={handleConfirm} disabled={!comment.trim() || saving}>
            {saving ? "Wird gespeichert…" : "Übernehmen"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Requirement row (accordion item)
// ---------------------------------------------------------------------------

interface RequirementRowProps {
  row: Requirement
  isExpanded: boolean
  onToggle: () => void
  onConfirm: (id: string) => void
  onOpenOverride: (id: string) => void
  onOpenEvidence: (card: EvidenceCard) => void
}

function RequirementRow({
  row,
  isExpanded,
  onToggle,
  onConfirm,
  onOpenOverride,
  onOpenEvidence,
}: RequirementRowProps) {
  const noEvidence = row.evidence === null
  const effectiveStatus: MachineStatus = row.override
    ? row.override.newStatus
    : noEvidence
    ? "open"
    : row.machineStatus

  return (
    <div className="border-b border-border last:border-0">
      {/* Row summary — min-height 44px */}
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          "flex w-full items-center gap-3 px-5 py-3 text-left transition-colors",
          "min-h-[44px] hover:bg-muted/40",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        )}
        aria-expanded={isExpanded}
      >
        {isExpanded ? (
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        )}
        <MachineStatusBadge
          status={effectiveStatus}
          label={REQUIREMENT_STATUS_LABELS[effectiveStatus]}
          className="shrink-0"
        />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-sm font-medium text-foreground">{row.title}</span>
          <span className="truncate text-xs text-muted-foreground">{row.reason}</span>
        </div>
        {row.override && (
          <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            Manuell angepasst
          </span>
        )}
        {noEvidence && !row.override && (
          <span className="shrink-0 rounded-full bg-status-partial/10 px-2 py-0.5 text-xs text-status-partial">
            Kein Beleg
          </span>
        )}
      </button>

      {/* Expanded panel */}
      {isExpanded && (
        <div className="flex flex-col gap-4 border-t border-border bg-muted/20 px-5 pb-5 pt-4">
          {/* Detail text */}
          <p className="text-sm leading-relaxed text-foreground">{row.detail}</p>

          {/* No-evidence hint */}
          {noEvidence && (
            <div className="flex items-center gap-2 rounded-md border border-status-partial/30 bg-status-partial/8 px-3 py-2">
              <AlertTriangle className="size-4 shrink-0 text-status-partial" />
              <p className="text-sm text-foreground">
                Kein Beleg gefunden — bitte prüfen.
              </p>
            </div>
          )}

          {/* Evidence chip */}
          {row.evidence && (() => {
            const card = dummyEvidence.find((c) => c.id === row.evidence!.evidenceCardId)
            return (
              <div>
                <button
                  type="button"
                  onClick={() => card && onOpenEvidence(card)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-foreground",
                    "transition-colors hover:bg-accent/60",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  )}
                >
                  {row.evidence.label}
                </button>
              </div>
            )
          })()}

          {/* Human layer — always shown when expanded, visually separated */}
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-card px-3 py-2.5">
            {row.humanCheck ? (
              <HumanCheckMark check={row.humanCheck} />
            ) : (
              <>
                <span className="mr-1 text-xs text-muted-foreground">Menschliche Prüfung:</span>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 gap-1.5 px-2.5 text-xs"
                  onClick={() => onConfirm(row.id)}
                >
                  <CheckCheck className="size-3.5" />
                  Bestätigen
                </Button>
                <button
                  type="button"
                  className="min-h-[32px] px-1.5 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => onOpenOverride(row.id)}
                >
                  <PenLine className="mr-1 inline size-3" />
                  Korrigieren
                </button>
              </>
            )}
          </div>

          {/* Override record */}
          {row.override && (
            <div className="rounded-md border border-border bg-card px-3 py-2">
              <p className="text-xs text-muted-foreground">
                Manuell angepasst von{" "}
                <span className="font-medium text-foreground">{row.override.byName}</span>
                {" · "}{row.override.timestamp}
              </p>
              <details className="mt-1">
                <summary className="cursor-pointer text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">
                  Kommentar ansehen
                </summary>
                <p className="mt-1.5 text-sm text-foreground">{row.override.comment}</p>
              </details>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Accordion group
// ---------------------------------------------------------------------------

interface GroupAccordionProps {
  group: RequirementGroup
  rows: Requirement[]
  expandedIds: Set<string>
  onToggle: (id: string) => void
  onConfirm: (id: string) => void
  onOpenOverride: (id: string) => void
  onOpenEvidence: (card: EvidenceCard) => void
}

function GroupAccordion({
  group,
  rows,
  expandedIds,
  onToggle,
  onConfirm,
  onOpenOverride,
  onOpenEvidence,
}: GroupAccordionProps) {
  const [open, setOpen] = React.useState(true)
  const verifiedCount = rows.filter(
    (r) => (r.override ? r.override.newStatus : (!r.evidence ? "open" : r.machineStatus)) === "verified"
  ).length

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center gap-3 border-b border-border bg-muted/30 px-5 py-3.5 text-left",
          "transition-colors hover:bg-muted/50",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        )}
        aria-expanded={open}
      >
        {open ? (
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        )}
        <h2 className="flex-1 text-sm font-semibold text-foreground">{group}</h2>
        <span className="text-xs text-muted-foreground">
          {verifiedCount} / {rows.length} Erfüllt
        </span>
      </button>

      {open && (
        <div>
          {rows.map((row) => (
            <RequirementRow
              key={row.id}
              row={row}
              isExpanded={expandedIds.has(row.id)}
              onToggle={() => onToggle(row.id)}
              onConfirm={onConfirm}
              onOpenOverride={onOpenOverride}
              onOpenEvidence={onOpenEvidence}
            />
          ))}
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="overflow-hidden rounded-lg border border-border">
          <div className="border-b border-border bg-muted/30 px-5 py-3.5">
            <Skeleton className="h-4 w-48" />
          </div>
          {[0, 1, 2].map((j) => (
            <div key={j} className="flex items-center gap-3 border-b border-border px-5 py-3 last:border-0">
              <Skeleton className="size-4 rounded-full" />
              <Skeleton className="h-5 w-20 rounded-full" />
              <div className="flex flex-1 flex-col gap-1.5">
                <Skeleton className="h-4 w-56" />
                <Skeleton className="h-3 w-80" />
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

interface EmptyStateProps {
  onStartAnalysis: () => void
}

function EmptyState({ onStartAnalysis }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed border-border bg-muted/20 px-6 py-16 text-center">
      <p className="max-w-sm text-sm text-muted-foreground">
        Die Anforderungen werden bei der Analyse erkannt. Starten Sie die Analyse unter Quellen &amp; Evidenz.
      </p>
      <Button onClick={onStartAnalysis} variant="outline">
        Analyse starten
      </Button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main screen component
// ---------------------------------------------------------------------------

interface RequirementsScreenProps {
  /** Demo: override page state for testing. */
  forceState?: PageState
  /** Initial rows; defaults to the local mock data when omitted. */
  requirements?: Requirement[]
}

export function RequirementsScreen({
  forceState,
  requirements,
}: RequirementsScreenProps) {
  const [pageState, setPageState] = React.useState<PageState>(forceState ?? "default")
  const [rows, setRows] = React.useState<Requirement[]>(
    requirements ?? initialRequirements
  )
  const [expandedIds, setExpandedIds] = React.useState<Set<string>>(new Set())
  const [statusFilter, setStatusFilter] = React.useState<ReqFilter>("all")
  const [search, setSearch] = React.useState("")

  // Override dialog state
  const [overrideDialogOpen, setOverrideDialogOpen] = React.useState(false)
  const [overrideTargetId, setOverrideTargetId] = React.useState<string | null>(null)

  // Evidence drawer state
  const [drawerOpen, setDrawerOpen] = React.useState(false)
  const [drawerCard, setDrawerCard] = React.useState<EvidenceCard | null>(null)

  // Debug state toggling
  const [showDebug, setShowDebug] = React.useState(false)

  const isStopped = pageState === "stopped" || (!forceState && runState.isStopped)

  function toggleRow(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function handleConfirm(id: string) {
    setRows((prev) =>
      prev.map((r) =>
        r.id === id
          ? { ...r, humanCheck: { name: "Anna Keller", timestamp: "gerade eben" } }
          : r
      )
    )
  }

  function handleOpenOverride(id: string) {
    setOverrideTargetId(id)
    setOverrideDialogOpen(true)
  }

  function handleOverrideConfirm(newStatus: MachineStatus, comment: string) {
    if (!overrideTargetId) return
    setRows((prev) =>
      prev.map((r) =>
        r.id === overrideTargetId
          ? {
              ...r,
              override: {
                byName: "Anna Keller",
                newStatus,
                comment,
                timestamp: "gerade eben",
              },
              // Clear any prior human check — override supersedes it
              humanCheck: undefined,
            }
          : r
      )
    )
    setOverrideTargetId(null)
  }

  function handleOpenEvidence(card: EvidenceCard) {
    setDrawerCard(card)
    setDrawerOpen(true)
  }

  // Status summary + filter chips run through the shared view model so the
  // wording stays consistent with the live screen.
  const summary = summarize(rows.map(rowView))
  const availableFilters = REQ_FILTER_ORDER.filter(
    (f) => f !== "all" && rows.some((r) => matchesFilter(rowView(r), f))
  )

  const query = search.trim().toLowerCase()
  const filteredRows = rows.filter((r) => {
    if (!matchesFilter(rowView(r), statusFilter)) return false
    if (query && !`${r.title} ${r.reason}`.toLowerCase().includes(query))
      return false
    return true
  })

  const openCount = summary.open + summary.partial + summary.blocked

  const overrideTarget = rows.find((r) => r.id === overrideTargetId)

  // ── Render ──

  return (
    <div className="flex min-h-full flex-col">
      {/* Scrollable content */}
      <div className="flex-1 px-6 py-8 pb-32">
        <div className="mx-auto flex max-w-4xl flex-col gap-6">
          {/* Page header */}
          <div className="flex flex-col gap-1">
            {/* h2: Seiten-h1 ist «Analyse & Recherche» (app/anforderungen). */}
            <h2 className="text-balance text-xl font-semibold text-foreground">
              Anforderungen &amp; Fördervoraussetzungen
            </h2>
            <p className="text-sm text-muted-foreground">
              Automatisch erkannte Voraussetzungen, Belege und offene Prüfpunkte
              für diesen Antrag.
            </p>
          </div>

          {pageState === "loading" && <LoadingSkeleton />}

          {pageState === "empty" && (
            <EmptyState onStartAnalysis={() => setPageState("default")} />
          )}

          {(pageState === "default" || pageState === "stopped") && (
            <>
              {/* Stopped banner */}
              {isStopped && <StoppedRunBanner stoppedAt={runState.stoppedAt} />}
              {isStopped && (
                <p className="text-xs text-muted-foreground">
                  Stand: unvollständiger Durchlauf
                </p>
              )}

              {/* Status summary */}
              <RequirementSummaryBar summary={summary} />

              {/* Filter chips + search */}
              <RequirementFilterBar
                available={availableFilters}
                value={statusFilter}
                onChange={setStatusFilter}
                search={search}
                onSearchChange={setSearch}
              />

              {/* Accordion groups */}
              <div className="flex flex-col gap-4">
                {GROUPS.map((group) => {
                  const groupRows = filteredRows.filter((r) => r.group === group)
                  if (groupRows.length === 0) return null
                  return (
                    <GroupAccordion
                      key={group}
                      group={group}
                      rows={groupRows}
                      expandedIds={expandedIds}
                      onToggle={toggleRow}
                      onConfirm={handleConfirm}
                      onOpenOverride={handleOpenOverride}
                      onOpenEvidence={handleOpenEvidence}
                    />
                  )
                })}
                {filteredRows.length === 0 && (statusFilter !== "all" || query) && (
                  <p className="py-8 text-center text-sm text-muted-foreground">
                    Keine Anforderungen entsprechen dem aktuellen Filter.
                  </p>
                )}
              </div>
            </>
          )}

          {/* Debug: state switcher — hidden from normal user-facing UI */}
          {SHOW_DEBUG_CONTROLS && (
            <div className="border-t border-border pt-6">
              <button
                type="button"
                onClick={() => setShowDebug((v) => !v)}
                className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
                aria-expanded={showDebug}
              >
                {showDebug ? (
                  <ChevronDown className="size-3.5" />
                ) : (
                  <ChevronRight className="size-3.5" />
                )}
                Demo: Seitenzustände testen
              </button>
              {showDebug && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {(["default", "loading", "empty", "stopped"] as PageState[]).map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setPageState(s)}
                      className={cn(
                        "inline-flex h-8 items-center rounded-full border border-border bg-card px-3 text-xs font-medium text-foreground transition-colors",
                        "hover:bg-accent hover:text-accent-foreground",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                        pageState === s && "bg-accent text-accent-foreground"
                      )}
                    >
                      {s === "default" && "Standard"}
                      {s === "loading" && "Laden (Skeleton)"}
                      {s === "empty" && "Leer"}
                      {s === "stopped" && "Gestoppter Durchlauf"}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Sticky footer — blocker-aware next step */}
      <footer className="sticky bottom-0 z-10 border-t border-border bg-background/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-6 py-4">
          {summary.blocked > 0 ? (
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-destructive">
                {summary.blocked} Blocker
              </span>{" "}
              {summary.blocked === 1 ? "verhindert" : "verhindern"} den nächsten
              Schritt.
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">
                {openCount} offene{openCount === 1 ? "r Punkt wird" : " Punkte werden"}
              </span>{" "}
              ins Review übernommen.
            </p>
          )}
          {summary.blocked > 0 ? (
            <Button disabled>Blocker zuerst klären</Button>
          ) : (
            <Button render={<a href="/editor" />} nativeButton={false}>
              Weiter zum Entwurf
            </Button>
          )}
        </div>
      </footer>

      {/* Override dialog */}
      <OverrideDialog
        open={overrideDialogOpen}
        onOpenChange={setOverrideDialogOpen}
        rowTitle={overrideTarget?.title ?? ""}
        onConfirm={handleOverrideConfirm}
      />

      {/* Evidence drawer */}
      <EvidenceDrawer
        card={drawerCard}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </div>
  )
}
