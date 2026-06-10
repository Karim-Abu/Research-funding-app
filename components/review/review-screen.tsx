"use client"

import * as React from "react"
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  ArrowRight,
  Clock,
  RotateCcw,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { MachineStatusBadge } from "@/components/status/machine-status-badge"
import { cn } from "@/lib/utils"
import type { MachineStatus } from "@/lib/types"
import {
  GATE_ROWS,
  FINDINGS,
  DEFAULT_APPROVAL,
  PAGE_SCENARIOS,
  type GateRow,
  type GateStatus,
  type Finding,
  type FindingSeverity,
  type ApprovalData,
  type ApprovalState,
  type PageScenario,
} from "@/lib/review-mock-data"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function gateStatusToMachineStatus(s: GateStatus): MachineStatus {
  if (s === "passed") return "verified"
  if (s === "partial") return "partial"
  return "blocker"
}

function gateLabel(s: GateStatus) {
  if (s === "passed") return "Bestanden"
  if (s === "partial") return "Teilweise"
  return "Nicht bestanden"
}

const SEVERITY_CONFIG: Record<
  FindingSeverity,
  { label: string; className: string; icon: React.ElementType }
> = {
  blocker: {
    label: "Blockierend",
    className: "bg-status-blocker/12 text-status-blocker",
    icon: XCircle,
  },
  important: {
    label: "Wichtig",
    className: "bg-status-partial/12 text-status-partial",
    icon: AlertTriangle,
  },
  hint: {
    label: "Hinweis",
    className: "bg-muted text-muted-foreground",
    icon: ChevronRight,
  },
}

// ---------------------------------------------------------------------------
// Donut progress chart (inline SVG, no chart lib)
// ---------------------------------------------------------------------------

function DonutChart({ percent }: { percent: number }) {
  const r = 32
  const cx = 40
  const cy = 40
  const circumference = 2 * Math.PI * r
  const filled = (percent / 100) * circumference
  const gap = circumference - filled

  return (
    <svg
      width="80"
      height="80"
      viewBox="0 0 80 80"
      aria-hidden="true"
      className="shrink-0"
    >
      {/* Track */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        strokeWidth="10"
        className="stroke-border"
      />
      {/* Progress */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        strokeWidth="10"
        className="stroke-status-fulfilled"
        strokeLinecap="round"
        strokeDasharray={`${filled} ${gap}`}
        strokeDashoffset={circumference / 4}
        transform={`rotate(-90 ${cx} ${cy})`}
        style={{ transformOrigin: `${cx}px ${cy}px` }}
      />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Gate row
// ---------------------------------------------------------------------------

function GateRowItem({ row }: { row: GateRow }) {
  const [expanded, setExpanded] = React.useState(false)
  const machineStatus = gateStatusToMachineStatus(row.status)

  return (
    <div className="rounded-md border border-border bg-card">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full min-h-[52px] items-start gap-3 px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
        aria-expanded={expanded}
      >
        <MachineStatusBadge
          status={machineStatus}
          label={gateLabel(row.status)}
          className="mt-0.5 shrink-0"
        />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-sm font-medium text-foreground">{row.label}</span>
          <span className="text-xs text-muted-foreground">{row.result}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2 pl-2">
          {row.stale && (
            <span className="inline-flex items-center gap-1 rounded border border-status-partial/40 bg-status-partial/8 px-2 py-0.5 text-xs text-status-partial">
              <Clock className="size-3" />
              Stand: unvollständiger Durchlauf
            </span>
          )}
          {expanded ? (
            <ChevronDown className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border bg-muted/20 px-4 pb-4 pt-3 flex flex-col gap-2">
          <p className="text-sm leading-relaxed text-foreground">{row.detail}</p>
          <a
            href="#"
            onClick={(e) => e.preventDefault()}
            className="inline-flex items-center gap-1 self-start text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            <ArrowRight className="size-3" />
            Zum Abschnitt: {row.jumpSection}
          </a>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Finding row
// ---------------------------------------------------------------------------

interface FindingRowProps {
  finding: Finding
  onMarkResolved: (id: string) => void
}

function FindingRow({ finding, onMarkResolved }: FindingRowProps) {
  const cfg = SEVERITY_CONFIG[finding.severity]
  const Icon = cfg.icon

  return (
    <div
      className={cn(
        "flex min-h-[52px] flex-col gap-1 rounded-md border border-border bg-card px-4 py-3",
        finding.state === "resolved" && "opacity-60"
      )}
    >
      <div className="flex flex-wrap items-start gap-2">
        <span
          className={cn(
            "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
            cfg.className
          )}
        >
          <Icon className="size-3.5" />
          {cfg.label}
        </span>
        <span className="text-sm font-medium text-foreground">{finding.title}</span>
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">
        {finding.description}
      </p>
      <div className="mt-1 flex items-center gap-3">
        <a
          href="#"
          onClick={(e) => e.preventDefault()}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          <ArrowRight className="size-3" />
          Zum Abschnitt: {finding.jumpSection}
        </a>
        {finding.state === "open" && (
          <button
            type="button"
            onClick={() => onMarkResolved(finding.id)}
            className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Als erledigt markieren
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Approval card
// ---------------------------------------------------------------------------

interface ApprovalCardProps {
  approval: ApprovalData
  blockerCount: number
  onApprove: () => void
  onRequestChanges: (comment: string) => void
  onReApprove: () => void
}

function ApprovalCard({
  approval,
  blockerCount,
  onApprove,
  onRequestChanges,
  onReApprove,
}: ApprovalCardProps) {
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [comment, setComment] = React.useState("")
  const [saving, setSaving] = React.useState(false)

  function handleRequestChanges() {
    if (!comment.trim()) return
    setSaving(true)
    setTimeout(() => {
      setSaving(false)
      onRequestChanges(comment)
      setDialogOpen(false)
      setComment("")
    }, 600)
  }

  const isBlocked = approval.state === "blocked" || blockerCount > 0

  return (
    <>
      <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-foreground">Ihre Freigabe</h2>

        {/* Approved */}
        {approval.state === "approved" && (
          <div className="flex flex-col gap-1">
            <span className="inline-flex items-center gap-1.5 text-sm font-medium text-human">
              <CheckCircle2 className="size-4" />
              Review freigegeben durch {approval.approvedBy} · {approval.approvedAt}
            </span>
            <p className="text-xs text-muted-foreground">
              Dies ist keine Einreichfreigabe.
            </p>
          </div>
        )}

        {/* Stale */}
        {approval.state === "stale" && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1 rounded-md border border-status-partial/40 bg-status-partial/8 px-3 py-2.5">
              <span className="text-sm font-medium text-status-partial">
                Freigabe veraltet — seitdem geändert.
              </span>
              <span className="text-xs text-muted-foreground">
                Ursprünglich freigegeben durch{" "}
                <span className="text-foreground">{approval.approvedBy}</span>{" "}
                am {approval.approvedAt}
              </span>
            </div>
            <Button onClick={onReApprove} className="self-start">
              <RotateCcw className="mr-1.5 size-4" />
              Erneut freigeben
            </Button>
          </div>
        )}

        {/* Changes requested */}
        {approval.state === "changes_requested" && (
          <div className="flex flex-col gap-2 rounded-md border border-status-partial/40 bg-status-partial/8 px-3 py-2.5">
            <span className="text-sm font-medium text-status-partial">
              Änderungen nötig — Kommentar von {approval.changesRequestedBy} ansehen
            </span>
            {approval.changesRequestedComment && (
              <details>
                <summary className="cursor-pointer text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">
                  Kommentar einblenden
                </summary>
                <p className="mt-2 text-sm text-foreground">
                  {approval.changesRequestedComment}
                </p>
              </details>
            )}
          </div>
        )}

        {/* Blocked or open */}
        {(approval.state === "blocked" || approval.state === "open") && (
          <div className="flex flex-col gap-3">
            {/* Self-review hint */}
            {approval.selfReview && (
              <p className="text-xs text-muted-foreground">
                Selbstprüfung — zweite Prüfung empfohlen.
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <Button
                disabled={isBlocked}
                onClick={onApprove}
                className="shrink-0"
              >
                Review freigeben
              </Button>
              {!isBlocked && (
                <Button
                  variant="outline"
                  onClick={() => setDialogOpen(true)}
                  className="shrink-0"
                >
                  Änderungen nötig
                </Button>
              )}
            </div>

            {isBlocked && blockerCount > 0 && (
              <p className="text-xs text-status-blocker">
                Freigabe nicht möglich:{" "}
                <span className="font-medium">
                  {blockerCount} blockierende{" "}
                  {blockerCount === 1 ? "Punkt" : "Punkte"} offen.
                </span>{" "}
                <a
                  href="#blockers"
                  onClick={(e) => e.preventDefault()}
                  className="underline underline-offset-2 hover:no-underline"
                >
                  Zu den Hinweisen
                </a>
              </p>
            )}
          </div>
        )}
      </div>

      {/* "Änderungen nötig" dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>Änderungen nötig</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <p className="text-sm text-muted-foreground">
              Beschreiben Sie, welche Änderungen erforderlich sind. Der Kommentar
              ist für alle Projektmitglieder sichtbar.
            </p>
            <Textarea
              placeholder="Kommentar (Pflichtfeld)…"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={4}
              className="resize-none text-sm"
            />
          </div>
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setDialogOpen(false)
                setComment("")
              }}
              disabled={saving}
            >
              Abbrechen
            </Button>
            <Button
              onClick={handleRequestChanges}
              disabled={!comment.trim() || saving}
            >
              {saving ? "Wird gespeichert…" : "Rückmeldung senden"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function ReviewSkeleton() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-8">
      <div className="flex items-start gap-6">
        <Skeleton className="size-20 rounded-full" />
        <div className="flex flex-col gap-2">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-64" />
        </div>
      </div>
      {[1, 2, 3, 4, 5].map((i) => (
        <Skeleton key={i} className="h-14 w-full rounded-md" />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

export interface ReviewScreenProps {
  /** Scenario override for the debug panel. Defaults to "default". */
  scenario?: PageScenario
}

export function ReviewScreen({ scenario = "default" }: ReviewScreenProps) {
  // Gate rows (local state so "resolved" markings persist)
  const [gates] = React.useState(GATE_ROWS)

  // Findings: start with mock, allow optimistic mark-resolved
  const [findings, setFindings] = React.useState(FINDINGS)

  function markFindingResolved(id: string) {
    setFindings((prev) =>
      prev.map((f) => (f.id === id ? { ...f, state: "resolved" as const } : f))
    )
  }

  // Approval state (driven by scenario)
  const [approval, setApproval] = React.useState<ApprovalData>(() =>
    scenarioToApproval(scenario)
  )
  // Re-sync when scenario changes (debug switcher)
  React.useEffect(() => {
    setApproval(scenarioToApproval(scenario))
    setFindings(FINDINGS)
  }, [scenario])

  // Derived counts
  const openBlockers = findings.filter(
    (f) => f.severity === "blocker" && f.state === "open"
  ).length
  const openFindings = findings.filter(
    (f) => f.severity !== "blocker" && f.state === "open"
  )
  const resolvedFindings = findings.filter((f) => f.state === "resolved")
  const visibleOpen = openFindings.slice(0, 5)
  const hiddenOpen = openFindings.slice(5)
  const [showMore, setShowMore] = React.useState(false)

  // Header counters
  const totalRows = gates.length
  const passedCount = gates.filter((g) => g.status === "passed").length
  const partialCount = gates.filter((g) => g.status === "partial").length
  const failedCount = gates.filter((g) => g.status === "failed").length

  // Empty state
  if (scenario === "empty") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-16 text-center">
        <p className="text-base font-medium text-foreground">
          Noch keine Prüfergebnisse vorhanden
        </p>
        <p className="max-w-md text-sm text-muted-foreground">
          Das Review startet, sobald eine Analyse gelaufen ist und Entwürfe
          vorliegen.
        </p>
      </div>
    )
  }

  // Stopped run banner (above content)
  const showStoppedBanner = scenario === "stopped_run"

  return (
    <div className="flex flex-col pb-16">
      {showStoppedBanner && (
        <div className="border-b border-status-partial/40 bg-status-partial/8 px-6 py-3">
          <p className="text-sm text-status-partial">
            <AlertTriangle className="mr-1.5 inline size-4 align-text-bottom" />
            Durchlauf gestoppt: Kostenlimit erreicht. Bisherige Ergebnisse sind
            gespeichert.
          </p>
        </div>
      )}

      <div className="mx-auto w-full max-w-5xl px-6 py-8">
        {/* Page header */}
        <div className="mb-8 flex flex-col gap-1">
          <h1 className="text-balance text-2xl font-semibold text-foreground">
            Review
          </h1>
          <p className="text-sm text-muted-foreground">
            Qualitätsprüfungen, Hinweise und Freigabe für diesen Antrag.
          </p>
        </div>

        {/* Two-column layout: main left, approval card right */}
        <div className="flex gap-8">
          {/* Main column */}
          <div className="flex min-w-0 flex-1 flex-col gap-10">

            {/* Progress summary */}
            <section aria-labelledby="progress-heading">
              <div className="flex items-center gap-5">
                <div className="relative flex items-center justify-center">
                  <DonutChart percent={78} />
                  <span className="pointer-events-none absolute text-[10px] font-semibold text-foreground leading-tight text-center">
                    78 %
                  </span>
                </div>
                <div className="flex flex-col gap-1">
                  <h2
                    id="progress-heading"
                    className="text-sm font-medium text-foreground"
                  >
                    Bearbeitungsstand: 78 %
                  </h2>
                  <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                    <span>
                      <span className="font-medium text-status-fulfilled">
                        {passedCount} Bestanden
                      </span>
                    </span>
                    <span>
                      <span className="font-medium text-status-partial">
                        {partialCount} Teilweise
                      </span>
                    </span>
                    <span>
                      <span className="font-medium text-status-blocker">
                        {failedCount} Nicht bestanden
                      </span>
                    </span>
                  </div>
                </div>
              </div>
            </section>

            <Separator />

            {/* Qualitätsprüfungen */}
            <section aria-labelledby="gates-heading">
              <h2
                id="gates-heading"
                className="mb-4 text-base font-semibold text-foreground"
              >
                Qualitätsprüfungen
              </h2>
              <div className="flex flex-col gap-2">
                {gates.map((row) => (
                  <GateRowItem key={row.id} row={row} />
                ))}
              </div>
            </section>

            <Separator />

            {/* Hinweise */}
            <section aria-labelledby="findings-heading" id="blockers">
              <h2
                id="findings-heading"
                className="mb-4 text-base font-semibold text-foreground"
              >
                Hinweise
              </h2>
              <div className="flex flex-col gap-2">
                {/* Blockers — always at top, always visible */}
                {findings
                  .filter((f) => f.severity === "blocker" && f.state === "open")
                  .map((f) => (
                    <FindingRow
                      key={f.id}
                      finding={f}
                      onMarkResolved={markFindingResolved}
                    />
                  ))}

                {/* Divider between blockers and open */}
                {openBlockers > 0 && openFindings.length > 0 && (
                  <Separator className="my-1" />
                )}

                {/* First 5 open non-blocker findings */}
                {visibleOpen.map((f) => (
                  <FindingRow
                    key={f.id}
                    finding={f}
                    onMarkResolved={markFindingResolved}
                  />
                ))}

                {/* "Weitere Hinweise anzeigen" */}
                {hiddenOpen.length > 0 && (
                  <>
                    {showMore &&
                      hiddenOpen.map((f) => (
                        <FindingRow
                          key={f.id}
                          finding={f}
                          onMarkResolved={markFindingResolved}
                        />
                      ))}
                    <button
                      type="button"
                      onClick={() => setShowMore((v) => !v)}
                      className="self-start text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {showMore
                        ? "Weniger anzeigen"
                        : `Weitere Hinweise anzeigen (${hiddenOpen.length})`}
                    </button>
                  </>
                )}

                {/* Resolved findings — collapsed */}
                {resolvedFindings.length > 0 && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">
                      Erledigt ({resolvedFindings.length})
                    </summary>
                    <div className="mt-2 flex flex-col gap-2">
                      {resolvedFindings.map((f) => (
                        <FindingRow
                          key={f.id}
                          finding={f}
                          onMarkResolved={markFindingResolved}
                        />
                      ))}
                    </div>
                  </details>
                )}
              </div>
            </section>
          </div>

          {/* Approval card — sticky right column */}
          <div className="w-72 shrink-0">
            <div className="sticky top-6">
              <ApprovalCard
                approval={approval}
                blockerCount={openBlockers}
                onApprove={() =>
                  setApproval({
                    state: "approved",
                    approvedBy: "Anna Keller",
                    approvedAt: "heute, 11:02",
                  })
                }
                onRequestChanges={(comment) =>
                  setApproval({
                    state: "changes_requested",
                    changesRequestedBy: "Anna Keller",
                    changesRequestedComment: comment,
                  })
                }
                onReApprove={() =>
                  setApproval({
                    state: "approved",
                    approvedBy: "Anna Keller",
                    approvedAt: "heute, 11:02",
                  })
                }
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Scenario → approval data mapper
// ---------------------------------------------------------------------------

function scenarioToApproval(scenario: PageScenario): ApprovalData {
  switch (scenario) {
    case "all_clear":
      return { state: "open", selfReview: true }
    case "approved":
      return {
        state: "approved",
        approvedBy: "Anna Keller",
        approvedAt: "heute, 11:02",
      }
    case "stale":
      return {
        state: "stale",
        approvedBy: "Anna Keller",
        approvedAt: "12. Mai 2026, 14:30",
      }
    case "changes_requested":
      return {
        state: "changes_requested",
        changesRequestedBy: "Bruno Steiner",
        changesRequestedComment:
          "Bitte den Abschnitt «Projektziel» kürzen und die fehlenden Belege für Kernaussagen ergänzen.",
      }
    default:
      return DEFAULT_APPROVAL
  }
}
