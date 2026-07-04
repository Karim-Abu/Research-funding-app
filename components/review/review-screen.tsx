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
import { FieldReview } from "@/components/review/field-review"
import { ProgressRing } from "@/components/review/review-progress-card"
import { cn } from "@/lib/utils"
import type { MachineStatus } from "@/lib/types"
import {
  DEFAULT_APPROVAL,
  PAGE_SCENARIOS,
  type ApprovalData,
  type ApprovalState,
  type PageScenario,
} from "@/lib/review-mock-data"
import {
  submitReview,
  countOpenBlockers,
  deriveGatesFromIssues,
  ApiError,
  BRIDGE_UNREACHABLE_MESSAGE,
} from "@/lib/api"
import { getCurrentRunId } from "@/lib/intake-store"
import { DataClassBadge } from "@/components/status/data-class-badge"
import type { DataClass } from "@/lib/types"
import type {
  GateRowDto,
  IssueDto,
  PortalFieldDraftDto,
  ReviewDecisionDto,
  RunFieldsDto,
} from "@/lib/backend-contract"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function gateStatusToMachineStatus(s: GateRowDto["status"]): MachineStatus {
  if (s === "passed") return "verified"
  if (s === "partial") return "partial"
  return "blocker"
}

function gateLabel(s: GateRowDto["status"]) {
  if (s === "passed") return "Bestanden"
  if (s === "partial") return "Teilweise bestanden"
  return "Nicht bestanden"
}

// ---------------------------------------------------------------------------
// Gate row
// ---------------------------------------------------------------------------

function GateRowItem({ row }: { row: GateRowDto }) {
  const [expanded, setExpanded] = React.useState(false)
  const machineStatus = gateStatusToMachineStatus(row.status)
  // No detail → nothing to expand; render a static row instead of an
  // accordion that would open empty.
  const expandable = Boolean(row.detail?.trim())

  const rowContent = (
    <>
      <MachineStatusBadge
        status={machineStatus}
        label={gateLabel(row.status)}
        className="mt-0.5 shrink-0"
      />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-sm font-medium text-foreground">{row.label}</span>
        <span className="text-xs text-muted-foreground">
          {row.result || "Keine offenen Befunde in dieser Prüfung."}
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-2 pl-2">
        {row.stale && (
          <span className="inline-flex items-center gap-1 rounded border border-status-partial/40 bg-status-partial/8 px-2 py-0.5 text-xs text-status-partial">
            <Clock className="size-3" />
            Stand: unvollständiger Durchlauf
          </span>
        )}
        {expandable &&
          (expanded ? (
            <ChevronDown className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground" />
          ))}
      </div>
    </>
  )

  if (!expandable) {
    return (
      <div className="rounded-md border border-border bg-card">
        <div className="flex w-full min-h-[52px] items-start gap-3 px-4 py-3">
          {rowContent}
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-md border border-border bg-card">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full min-h-[52px] items-start gap-3 px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
        aria-expanded={expanded}
      >
        {rowContent}
      </button>

      {expanded && (
        <div className="border-t border-border bg-muted/20 px-4 pb-4 pt-3">
          <p className="text-sm leading-relaxed text-foreground">{row.detail}</p>
        </div>
      )}
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
  findingsRef: React.RefObject<HTMLElement | null>
}

function ApprovalCard({
  approval,
  blockerCount,
  onApprove,
  onRequestChanges,
  onReApprove,
  findingsRef,
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

  function scrollToBlockers() {
    if (!findingsRef.current) return
    findingsRef.current.scrollIntoView({ behavior: "smooth", block: "start" })
    // Briefly highlight the section heading
    const el = findingsRef.current
    el.classList.add("ring-2", "ring-status-blocker", "ring-offset-2", "rounded-md")
    setTimeout(() => {
      el.classList.remove("ring-2", "ring-status-blocker", "ring-offset-2", "rounded-md")
    }, 2000)
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
              {/* Blocked: visually disabled with cursor-not-allowed but still renders reason */}
              {isBlocked ? (
                <span
                  role="button"
                  aria-disabled="true"
                  className={cn(
                    "inline-flex h-9 shrink-0 items-center justify-center rounded-md px-4 py-2",
                    "text-sm font-medium",
                    "border border-border bg-muted text-muted-foreground",
                    "cursor-not-allowed select-none opacity-60"
                  )}
                >
                  Prüfung abschliessen
                </span>
              ) : (
                <Button onClick={onApprove} className="shrink-0">
                  Prüfung abschliessen
                </Button>
              )}
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
                <button
                  type="button"
                  onClick={scrollToBlockers}
                  className="underline underline-offset-2 hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
                >
                  Zu den Hinweisen
                </button>
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
  /** Feldentwürfe + Issues (von api.getRunFields geladen). */
  initialData?: RunFieldsDto
  /** Datenklasse des Laufs (Badge im Kopf). */
  dataClass?: DataClass
}

export function ReviewScreen({
  scenario = "default",
  initialData,
  dataClass,
}: ReviewScreenProps) {
  // Feldentwürfe + Issues — Mutationen laufen über api.submitReview.
  const [fields, setFields] = React.useState<PortalFieldDraftDto[]>(
    initialData?.fields ?? []
  )
  const [issues, setIssues] = React.useState<IssueDto[]>(
    initialData?.issues ?? []
  )
  // Gates kommen aus dem Contract; liefert die Bridge keine, leiten wir sie
  // aus den Issues ab — nie hartkodierte Gates neben echten Feldern.
  const [gates, setGates] = React.useState<GateRowDto[]>(
    initialData?.gates ?? deriveGatesFromIssues(initialData?.issues ?? [])
  )
  const [reviewBusy, setReviewBusy] = React.useState(false)
  const [reviewError, setReviewError] = React.useState<string | null>(null)

  async function applyDecision(decision: ReviewDecisionDto) {
    setReviewBusy(true)
    setReviewError(null)
    try {
      const dto = await submitReview(getCurrentRunId(), decision)
      setFields(dto.fields)
      setIssues(dto.issues)
      setGates(dto.gates ?? deriveGatesFromIssues(dto.issues))
    } catch (e) {
      setReviewError(
        e instanceof ApiError ? e.message : BRIDGE_UNREACHABLE_MESSAGE
      )
    } finally {
      setReviewBusy(false)
    }
  }

  // Ref for the Feldentwürfe section — used by "Zu den Hinweisen" scroll
  const findingsRef = React.useRef<HTMLElement | null>(null)

  // Approval state (driven by scenario)
  const [approval, setApproval] = React.useState<ApprovalData>(() =>
    scenarioToApproval(scenario)
  )
  // Re-sync when scenario changes (debug switcher)
  React.useEffect(() => {
    setApproval(scenarioToApproval(scenario))
  }, [scenario])

  // Freigabe-Gating: offene, nicht überschriebene Blocker-Issues.
  const openBlockers = countOpenBlockers(issues)

  // "blocked" leitet sich aus den tatsächlichen Blockern ab — sind alle
  // entschieden, wird die Freigabe möglich ("open"), ohne das Szenario
  // (approved/stale/changes_requested) zu überschreiben.
  const effectiveApproval: ApprovalData =
    approval.state === "blocked" && openBlockers === 0
      ? { ...approval, state: "open" }
      : approval

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

      <div className="mx-auto w-full max-w-6xl px-6 py-8">
        {/* Page header */}
        <div className="mb-8 flex flex-col gap-2">
          <h1 className="text-balance text-2xl font-semibold text-foreground">
            Qualitätsprüfung
          </h1>
          <p className="text-sm text-muted-foreground">
            Qualitätsprüfungen, Hinweise und Freigabe für diesen Antrag.
          </p>
          {dataClass && <DataClassBadge dataClass={dataClass} />}
        </div>

        <div className="flex min-w-0 flex-col gap-10">
            {/* Progress summary — real gate counts, no hardcoded percent. */}
            <section aria-labelledby="progress-heading">
              <div className="flex flex-col items-center gap-4 sm:flex-row sm:gap-5">
                <ProgressRing
                  segments={[
                    { value: passedCount, className: "text-status-fulfilled" },
                    { value: partialCount, className: "text-status-partial" },
                    { value: failedCount, className: "text-destructive" },
                  ]}
                  total={totalRows}
                  centerValue={`${passedCount} / ${totalRows}`}
                  centerLabel="Prüfbereiche bestanden"
                  ariaLabel={`Bearbeitungs- und Prüfstand: ${passedCount} von ${totalRows} Prüfbereichen bestanden, ${partialCount} teilweise bestanden, ${failedCount} nicht bestanden.`}
                  size={96}
                  strokeWidth={9}
                />
                <div className="flex flex-col gap-1">
                  <h2
                    id="progress-heading"
                    className="text-sm font-medium text-foreground"
                  >
                    Bearbeitungs- und Prüfstand
                  </h2>
                  <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                    <span>
                      <span className="font-medium text-status-fulfilled">
                        {passedCount} Bestanden
                      </span>
                    </span>
                    <span>
                      <span className="font-medium text-status-partial">
                        {partialCount} Teilweise bestanden
                      </span>
                    </span>
                    <span>
                      <span className="font-medium text-status-blocker">
                        {failedCount} Nicht bestanden
                      </span>
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Bearbeitungs- und Prüfstand — keine Aussage zur
                    Förderwahrscheinlichkeit.
                  </p>
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

            {/* Feldentwürfe — 3 Spalten: Felder / Text / Issues + Freigabe */}
            <section ref={findingsRef} aria-labelledby="fields-heading" id="blockers">
              <h2
                id="fields-heading"
                className="mb-4 text-base font-semibold text-foreground"
              >
                Feldentwürfe
              </h2>

              {reviewError && (
                <div
                  role="alert"
                  className="mb-4 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-foreground"
                >
                  <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
                  {reviewError}
                </div>
              )}

              <FieldReview
                fields={fields}
                issues={issues}
                busy={reviewBusy}
                onRecheck={(fieldId, text) =>
                  applyDecision({ decisions: [], fieldEdits: [{ fieldId, text }] })
                }
                onDecide={(decisions) => applyDecision({ decisions })}
                approvalSlot={
                  <ApprovalCard
                    approval={effectiveApproval}
                    blockerCount={openBlockers}
                    findingsRef={findingsRef}
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
                }
              />
            </section>
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
