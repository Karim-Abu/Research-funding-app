"use client"

import * as React from "react"
import {
  RefreshCw,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  ShieldCheck,
  ArrowRight,
  Sparkles,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { getCapabilities } from "@/lib/capabilities"
import { CanonicalStatusBadge } from "@/components/status/canonical-status"
import { QualitySummary } from "@/components/review/quality-summary"
import {
  GroupedFindingsSection,
  GroupRow,
  NextActionsCard,
} from "@/components/review/fix-queue"
import { useFixQueue, type GroupedFindingDto } from "@/lib/fix-queue"
import {
  useCheckStatus,
  areaProgress,
  checkStateLabel,
  notRunReasonLabel,
  CHECK_AREA_LABELS,
  CHECK_AREA_DESCRIPTIONS,
  CHECK_STATE_STYLE,
  type CheckAreaStatusDto,
} from "@/lib/check-status"
import {
  getReview,
  startRecheck,
  createApproval,
  ReviewError,
  type ReviewPackageDto,
  type ReviewFindingDto,
} from "@/lib/review"
import { ReviewProgressCard } from "@/components/review/review-progress-card"
import {
  HUMAN_IN_THE_LOOP_NOTE,
  APPROVAL_SCOPE_NOTE,
  REVIEW_SEVERITY_LABELS,
  REVIEW_SEVERITY_STYLE,
  fieldLabel,
  aiFindings,
  reliabilityStaleFinding,
  humanReviewCount,
  AI_FINDINGS_LABEL,
  AI_FINDINGS_DESCRIPTION,
} from "@/lib/review-view"

function disabledReasons(pkg: ReviewPackageDto): string[] {
  const reasons: string[] = []
  if (pkg.recheck_required) reasons.push("Erneute Prüfung erforderlich")
  if (pkg.blocker_count > 0) reasons.push(`${pkg.blocker_count} Blocker offen`)
  const blockerIssues = pkg.open_issues.filter((i) => i.severity === "blocker").length
  if (blockerIssues > 0) reasons.push(`${blockerIssues} blockierende Anforderung(en)`)
  return reasons
}

export function LiveReview({ runId }: { runId: string }) {
  const [pkg, setPkg] = React.useState<ReviewPackageDto | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [notice, setNotice] = React.useState<string | null>(null)
  const [reliabilityEnabled, setReliabilityEnabled] = React.useState(false)

  React.useEffect(() => {
    void getCapabilities().then((c) =>
      setReliabilityEnabled(Boolean(c.features?.reliability))
    )
  }, [])

  const load = React.useCallback(() => {
    setError(null)
    getReview(runId)
      .then(setPkg)
      .catch((e) => setError(e instanceof Error ? e.message : "Review nicht ladbar."))
  }, [runId])

  React.useEffect(() => load(), [load])

  // Teil A5 — die neun Prüfbereiche kommen AUSSCHLIESSLICH aus dem
  // autoritativen Check-Status-View; die Aufgabenliste aus der Fix Queue.
  // Beide laden neu, sobald sich die Package-Version ändert.
  const { checks } = useCheckStatus(runId, pkg?.review_package_version)
  const { queue: fixQueue } = useFixQueue(runId, pkg?.review_package_version)

  async function recheck() {
    if (!pkg) return
    setBusy(true)
    setNotice(null)
    try {
      await startRecheck(runId, pkg.review_package_version)
      setNotice("Erneute Prüfung abgeschlossen.")
      load()
    } catch (e) {
      setError(e instanceof ReviewError ? e.message : "Prüfung fehlgeschlagen.")
    } finally {
      setBusy(false)
    }
  }

  async function approve() {
    if (!pkg) return
    setBusy(true)
    setNotice(null)
    setError(null)
    try {
      await createApproval(runId, pkg, "run", runId)
      setNotice("Prüfung abgeschlossen.")
      load()
    } catch (e) {
      setError(e instanceof ReviewError ? e.message : "Freigabe fehlgeschlagen.")
    } finally {
      setBusy(false)
    }
  }

  function jumpToTasks() {
    const firstFailed = checks?.areas.find((a) => a.status === "failed")
    const target = firstFailed
      ? document.getElementById(`area-${firstFailed.area}`)
      : document.querySelector('[data-testid="grouped-findings"]')
    target?.scrollIntoView({ behavior: "smooth", block: "center" })
  }

  if (error && !pkg) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button variant="outline" className="mt-4" onClick={load}>
          <RefreshCw data-icon="inline-start" />
          Erneut versuchen
        </Button>
      </div>
    )
  }
  if (pkg === null) {
    return (
      <div className="mx-auto flex max-w-4xl flex-col gap-3">
        <Skeleton className="h-8 w-48" />
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  const reasons = disabledReasons(pkg)
  const approvable = reasons.length === 0 && pkg.approval_status !== "approved"
  const staleReliability = reliabilityStaleFinding(pkg)
  const aiFinds = aiFindings(pkg)
  const hasBlockers = pkg.blocker_count > 0
  // «Blockierende Aufgaben» = gruppierte Aufgaben (B7); das Gate-Kriterium
  // bleibt pkg.blocker_count (dieselbe Backend-Zählung wie die Freigabe).
  const blockingTasks = checks?.blocking_task_count ?? pkg.blocker_count
  const exportArea = checks?.areas.find((a) => a.area === "export")
  const panelState: "blocked" | "warnings" | "ready" = hasBlockers
    ? "blocked"
    : exportArea?.status === "passed"
      ? "ready"
      : "warnings"
  // Gruppen je Prüfbereich (Join über GroupedFinding.area); Gruppen ohne
  // Bereich (z. B. menschliche Kommentare) erscheinen als eigene Liste.
  const groupsByArea = new Map<string, GroupedFindingDto[]>()
  const unassignedGroups: GroupedFindingDto[] = []
  for (const group of fixQueue?.grouped_findings ?? []) {
    if (group.area) {
      const list = groupsByArea.get(group.area) ?? []
      list.push(group)
      groupsByArea.set(group.area, list)
    } else {
      unassignedGroups.push(group)
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-balance text-2xl font-semibold text-foreground">
            Qualitätsprüfung
          </h1>
          <p className="text-sm text-muted-foreground">
            Prüft Pflichtfelder, Belege, Zeichenlimits, Platzhalter und offene
            Punkte vor Export oder Weiterbearbeitung.
          </p>
          {/* R1.3 — kanonischer Gesamtstatus; key erzwingt Neuladen nach
              Recheck/Freigabe (neue Package-Version). */}
          <div className="mt-1">
            <CanonicalStatusBadge
              key={pkg.review_package_version}
              runId={runId}
            />
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {/* Recheck always re-runs the WHOLE quality check — there is no
              per-finding recheck in the contract. */}
          <Button variant="outline" onClick={recheck} disabled={busy}>
            <RefreshCw data-icon="inline-start" />
            Gesamte Prüfung erneut ausführen
          </Button>
          {!hasBlockers && (
            <Button render={<a href="/export" />} nativeButton={false}>
              Weiter zum Export
            </Button>
          )}
        </div>
      </div>

      {pkg.recheck_required && (
        <p
          role="status"
          className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900"
        >
          Es liegen ungeprüfte Änderungen vor. Bitte führen Sie eine erneute
          Prüfung durch, bevor Sie freigeben.
        </p>
      )}
      {staleReliability && (
        <p
          role="status"
          data-testid="reliability-stale-banner"
          className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900"
        >
          Qualitätsprüfung veraltet — bitte erneut ausführen. Der Entwurf wurde
          seit der letzten Zuverlässigkeitsprüfung geändert; vor einer Freigabe
          ist eine neue Zuverlässigkeitsprüfung nötig.
        </p>
      )}
      {notice && (
        <p role="status" className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      {/* Bearbeitungs- und Prüfstand — Ring über die neun Prüfbereiche aus dem
          autoritativen Check-Status-View (Grau = nicht geprüft). */}
      {checks && (
        <ReviewProgressCard
          progress={areaProgress(checks.areas)}
          blockingTasks={checks.blocking_task_count}
          evidenceNotes={checks.evidence_note_count}
          pruefungNoetig={humanReviewCount(pkg)}
          recheckRequired={pkg.recheck_required}
        />
      )}

      {/* Nächste Aufgaben — Top-5 priorisiert aus der Fix Queue (Standard). */}
      {fixQueue && <NextActionsCard groups={fixQueue.next_actions} limit={5} />}

      {/* Approval / blocker panel */}
      <ApprovalPanel
        state={panelState}
        blockingTasks={blockingTasks}
        reasons={reasons}
        approvable={approvable}
        approved={pkg.approval_status === "approved"}
        busy={busy}
        onApprove={approve}
        onRecheck={recheck}
        onJumpToTasks={jumpToTasks}
      />

      <p className="flex items-start gap-2 text-xs text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />
        {HUMAN_IN_THE_LOOP_NOTE}
      </p>

      {/* Prüfbereiche — Status ausschliesslich aus dem Check-Status-View;
          pro Bereich die zugehörigen gruppierten Aufgaben. */}
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-foreground">Qualitätsprüfungen</h2>
        <div className="flex flex-col gap-2">
          {checks
            ? checks.areas.map((area) => (
                <CheckAreaRow
                  key={area.area}
                  area={area}
                  groups={groupsByArea.get(area.area) ?? []}
                  runId={runId}
                />
              ))
            : [1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      </section>

      {/* Gruppen ohne Prüfbereich (z. B. Kommentare aus der menschlichen
          Prüfung) — bleiben sichtbar, nur nicht bereichsgebunden. */}
      {unassignedGroups.length > 0 && (
        <GroupedFindingsSection groups={unassignedGroups} runId={runId} />
      )}

      {/* Fachliche A3-Prüfhinweise (advisory). */}
      {aiFinds.length > 0 && (
        <section className="flex flex-col gap-3" data-testid="ai-findings">
          <div className="flex flex-col gap-0.5">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Sparkles className="size-4 text-muted-foreground" />
              {AI_FINDINGS_LABEL}
            </h2>
            <p className="text-xs text-muted-foreground">{AI_FINDINGS_DESCRIPTION}</p>
          </div>
          <div className="flex flex-col gap-2">
            {aiFinds.map((f) => (
              <AiFindingCard key={f.finding_id} finding={f} />
            ))}
          </div>
        </section>
      )}

      {reliabilityEnabled && <QualitySummary runId={runId} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Approval / blocker panel — Zustand aus Gate (blocker_count) + Export-Bereich:
// blocked (rot), warnings («Mit Warnungen kopierbar», orange — nie grün als
// fachlich freigegeben) oder ready (grün).
// ---------------------------------------------------------------------------
function ApprovalPanel({
  state,
  blockingTasks,
  reasons,
  approvable,
  approved,
  busy,
  onApprove,
  onRecheck,
  onJumpToTasks,
}: {
  state: "blocked" | "warnings" | "ready"
  blockingTasks: number
  reasons: string[]
  approvable: boolean
  approved: boolean
  busy: boolean
  onApprove: () => void
  onRecheck: () => void
  onJumpToTasks: () => void
}) {
  const blocked = state === "blocked"
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-lg border px-5 py-4",
        blocked && "border-destructive/30 bg-destructive/5",
        state === "warnings" && "border-status-partial/30 bg-status-partial/5",
        state === "ready" && "border-status-fulfilled/30 bg-status-fulfilled/5"
      )}
    >
      <div className="flex items-center gap-2">
        {blocked ? (
          <AlertTriangle className="size-4 text-destructive" />
        ) : state === "warnings" ? (
          <AlertTriangle className="size-4 text-status-partial" />
        ) : (
          <CheckCircle2 className="size-4 text-status-fulfilled" />
        )}
        <h2 className="text-sm font-semibold text-foreground">
          {blocked
            ? "Freigabe blockiert"
            : state === "warnings"
              ? "Mit Warnungen kopierbar"
              : "Bereit für Export"}
        </h2>
      </div>

      <p className="text-sm text-muted-foreground">
        {blocked
          ? `Der Antrag kann noch nicht exportiert oder freigegeben werden, weil noch ${blockingTasks} blockierende Aufgabe${
              blockingTasks === 1 ? "" : "n"
            } zu klären ${blockingTasks === 1 ? "ist" : "sind"}.`
          : state === "warnings"
            ? "Keine blockierenden Punkte offen. Es bestehen aber offene Hinweise oder ungeprüfte Bereiche — der Antrag kann als Arbeitskopie kopiert werden, gilt jedoch nicht als fachlich freigegeben."
            : "Alle Prüfbereiche sind bestanden. Prüfen Sie den Entwurf final und fahren Sie mit dem Export fort."}
      </p>

      <div className="flex flex-wrap items-center gap-2">
        {blocked && (
          <Button variant="outline" size="sm" onClick={onJumpToTasks}>
            Zur ersten Aufgabe springen
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={onRecheck} disabled={busy}>
          <RefreshCw data-icon="inline-start" />
          Erneut prüfen
        </Button>
        {!blocked && (
          <Button size="sm" render={<a href="/export" />} nativeButton={false}>
            Weiter zum Export
            <ArrowRight className="ml-1.5 size-3.5" />
          </Button>
        )}
        {/* Human-controlled approval — never auto-approves. */}
        <Button size="sm" onClick={onApprove} disabled={busy || !approvable}>
          <CheckCircle2 data-icon="inline-start" />
          Prüfung abschliessen
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">{APPROVAL_SCOPE_NOTE}</p>

      {!approvable && !approved && reasons.length > 0 && (
        <ul className="text-xs text-muted-foreground">
          {reasons.map((r) => (
            <li key={r}>• {r}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Prüfbereichs-Zeile — Status ausschliesslich aus dem Check-Status-View
// (Grau = nicht geprüft, nie stillschweigend bestanden); aufklappbar mit den
// gruppierten Aufgaben des Bereichs.
// ---------------------------------------------------------------------------
function CheckAreaRow({
  area,
  groups,
  runId,
}: {
  area: CheckAreaStatusDto
  groups: GroupedFindingDto[]
  runId: string
}) {
  const [open, setOpen] = React.useState(area.status === "failed")
  const openFindings = area.open_blockers + area.open_warnings

  const summaryText =
    area.status === "not_run"
      ? notRunReasonLabel(area)
      : area.status === "passed"
        ? "Keine offenen Befunde in dieser Prüfung."
        : `${openFindings} Befund(e)`

  const statusChip = (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium",
        CHECK_STATE_STYLE[area.status]
      )}
    >
      {checkStateLabel(area)}
    </span>
  )
  const title = (
    <span className="min-w-0 flex-1">
      <span className="block text-sm font-medium text-foreground">
        {CHECK_AREA_LABELS[area.area]}
      </span>
      <span className="block truncate text-xs text-muted-foreground">
        {CHECK_AREA_DESCRIPTIONS[area.area]}
      </span>
    </span>
  )

  if (groups.length === 0) {
    return (
      <section
        id={`area-${area.area}`}
        data-testid="check-area"
        className="overflow-hidden rounded-lg border border-border bg-card"
      >
        <div className="flex w-full items-center gap-3 px-4 py-3">
          {statusChip}
          {title}
          <span className="shrink-0 text-xs text-muted-foreground">
            {summaryText}
          </span>
        </div>
      </section>
    )
  }

  return (
    <section
      id={`area-${area.area}`}
      data-testid="check-area"
      className="overflow-hidden rounded-lg border border-border bg-card"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        {open ? (
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        )}
        {statusChip}
        {title}
        <span className="shrink-0 text-xs text-muted-foreground">
          {summaryText}
        </span>
      </button>
      {open && (
        <div className="flex flex-col gap-2 border-t border-border bg-muted/20 px-4 py-3">
          {groups.map((group) => (
            <GroupRow key={group.group_key} group={group} runId={runId} />
          ))}
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Fachlicher A3-Prüfhinweis (advisory) — unverändert separat von den
// deterministischen Prüfbereichen.
// ---------------------------------------------------------------------------
function AiFindingCard({ finding }: { finding: ReviewFindingDto }) {
  return (
    <div className="rounded-md border border-border bg-card px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-foreground">{finding.description}</p>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${REVIEW_SEVERITY_STYLE[finding.severity]}`}
        >
          {REVIEW_SEVERITY_LABELS[finding.severity]}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{fieldLabel(finding.field_id)}</p>
      {finding.suggested_improvement && (
        <p className="mt-2 border-t border-border pt-2 text-xs text-muted-foreground">
          Vorschlag: {finding.suggested_improvement}
        </p>
      )}
    </div>
  )
}
