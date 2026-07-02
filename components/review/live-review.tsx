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
import { QualitySummary } from "@/components/review/quality-summary"
import {
  getReview,
  startRecheck,
  createApproval,
  ReviewError,
  type ReviewPackageDto,
  type ReviewFindingDto,
} from "@/lib/review"
import {
  REVIEW_FALLBACKS,
  HUMAN_IN_THE_LOOP_NOTE,
  REVIEW_SEVERITY_LABELS,
  REVIEW_SEVERITY_STYLE,
  GROUP_STATUS_LABELS,
  GROUP_STATUS_STYLE,
  groupFindings,
  summarizeReview,
  blockerBreakdown,
  fieldLabel,
  dedupeFindings,
  blockerRelevance,
  REVIEW_GROUP_LABELS,
  classifyFinding,
  aiFindings,
  deterministicFindings,
  reliabilityStaleFinding,
  AI_FINDINGS_LABEL,
  AI_FINDINGS_DESCRIPTION,
  type DedupedFinding,
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
  const [showTech, setShowTech] = React.useState(false)
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
      setNotice("Review freigegeben.")
      load()
    } catch (e) {
      setError(e instanceof ReviewError ? e.message : "Freigabe fehlgeschlagen.")
    } finally {
      setBusy(false)
    }
  }

  function jumpToFirstBlocker() {
    const first = pkg?.findings.find((f) => f.severity === "blocker")
    if (!first) return
    document
      .getElementById(`blocker-${first.finding_id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" })
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
  const summary = summarizeReview(pkg)
  const breakdown = blockerBreakdown(pkg)
  const hasBlockers = breakdown.blocker > 0
  // A3 (KI) findings are surfaced in their own section; the deterministic
  // quality-check groups, blocker cards and hints stay deterministic-only.
  const detFindings = deterministicFindings(pkg)
  const aiFinds = aiFindings(pkg)
  const groups = groupFindings(detFindings)
  const blockerFindings = detFindings.filter((f) => f.severity === "blocker")
  const warningFindings = detFindings.filter((f) => f.severity !== "blocker")
  const dedupedHints = dedupeFindings(warningFindings)

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
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="outline" onClick={recheck} disabled={busy}>
            <RefreshCw data-icon="inline-start" />
            Erneut prüfen
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

      {/* Summary */}
      <ReviewSummaryBar summary={summary} />

      {/* Nächste Schritte — the top actions derived from the current package */}
      <NextStepsCard
        pkg={pkg}
        staleReliability={Boolean(staleReliability)}
        groups={groups}
        busy={busy}
        onRecheck={recheck}
      />

      {/* Approval / blocker panel */}
      <ApprovalPanel
        hasBlockers={hasBlockers}
        breakdown={breakdown}
        reasons={reasons}
        approvable={approvable}
        approved={pkg.approval_status === "approved"}
        busy={busy}
        onApprove={approve}
        onRecheck={recheck}
        onJumpToBlocker={jumpToFirstBlocker}
      />

      <p className="flex items-start gap-2 text-xs text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />
        {HUMAN_IN_THE_LOOP_NOTE}
      </p>

      {/* Quality checks accordion */}
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-foreground">Qualitätsprüfungen</h2>
        <div className="flex flex-col gap-2">
          {groups.map((g) => (
            <GroupAccordion key={g.key} group={g} />
          ))}
        </div>
      </section>

      {/* Blocker cards */}
      {blockerFindings.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-foreground">Blocker</h2>
          <div className="flex flex-col gap-3">
            {blockerFindings.map((f) => (
              <BlockerCard key={f.finding_id} finding={f} onRecheck={recheck} />
            ))}
          </div>
        </section>
      )}

      {/* Deduplicated hints */}
      {dedupedHints.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-foreground">Hinweise</h2>
          <div className="flex flex-col gap-2">
            {dedupedHints.map((h) => (
              <DedupedHint key={h.description} hint={h} />
            ))}
          </div>
        </section>
      )}

      {/* KI-gestützte Hinweise (A3 evidence-consistency, advisory) */}
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

      {/* Technical details */}
      <div>
        <button
          type="button"
          onClick={() => setShowTech((v) => !v)}
          aria-expanded={showTech}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          {showTech ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          Technische Details
        </button>
        {showTech && (
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <dt>Prüfpaket-Version</dt>
            <dd className="font-mono">{pkg.review_package_version}</dd>
          </dl>
        )}
      </div>
      {reliabilityEnabled && <QualitySummary runId={runId} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Nächste Schritte — max 3 derived actions (recheck → stale reliability →
// dominant blocker group). Pure derivation from existing package data.
// ---------------------------------------------------------------------------
function NextStepsCard({
  pkg,
  staleReliability,
  groups,
  busy,
  onRecheck,
}: {
  pkg: ReviewPackageDto
  staleReliability: boolean
  groups: ReturnType<typeof groupFindings>
  busy: boolean
  onRecheck: () => void
}) {
  const steps: { key: string; text: string; action?: React.ReactNode }[] = []

  if (pkg.recheck_required) {
    steps.push({
      key: "recheck",
      text: "Ungeprüfte Änderungen — führen Sie eine erneute Prüfung durch.",
      action: (
        <Button size="xs" variant="outline" onClick={onRecheck} disabled={busy}>
          Erneut prüfen
        </Button>
      ),
    })
  }
  if (staleReliability) {
    steps.push({
      key: "reliability",
      text: "Qualitätsprüfung veraltet — führen Sie die Zuverlässigkeitsprüfung erneut aus.",
      action: (
        <Button
          size="xs"
          variant="outline"
          onClick={() =>
            document
              .querySelector('[data-testid="quality-summary"]')
              ?.scrollIntoView?.({ behavior: "smooth", block: "center" })
          }
        >
          Zur Qualitätsübersicht
        </Button>
      ),
    })
  }
  for (const group of groups) {
    if (steps.length >= 3) break
    if (group.status !== "nicht_bestanden") continue
    steps.push({
      key: group.key,
      text: `${group.label}: ${group.findings.length} Punkt(e) klären.`,
      action: (
        <Button size="xs" variant="outline" render={<a href="/editor" />} nativeButton={false}>
          Im Entwurf öffnen
        </Button>
      ),
    })
  }

  return (
    <section
      data-testid="next-steps"
      className="flex flex-col gap-2 rounded-lg border border-border bg-card px-5 py-4"
    >
      <h2 className="text-sm font-semibold text-foreground">Nächste Schritte</h2>
      {steps.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Keine offenen Schritte — prüfen Sie den Entwurf final und geben Sie das Review frei.
        </p>
      ) : (
        <ol className="flex flex-col gap-1.5">
          {steps.slice(0, 3).map((step, index) => (
            <li key={step.key} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted-foreground">{index + 1}.</span>
              <span className="min-w-0 flex-1 text-foreground">{step.text}</span>
              {step.action}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Summary bar
// ---------------------------------------------------------------------------
function ReviewSummaryBar({
  summary,
}: {
  summary: ReturnType<typeof summarizeReview>
}) {
  const tiles: { label: string; value: number; accent?: string }[] = [
    { label: "Bestanden", value: summary.bestanden, accent: "text-status-fulfilled" },
    { label: "Teilweise", value: summary.teilweise, accent: "text-status-partial" },
    {
      label: "Nicht bestanden",
      value: summary.nichtBestanden,
      accent: summary.nichtBestanden > 0 ? "text-destructive" : undefined,
    },
    {
      label: "Blocker",
      value: summary.blocker,
      accent: summary.blocker > 0 ? "text-destructive" : undefined,
    },
    { label: "Hinweise", value: summary.hinweise },
    { label: "Prüfung nötig", value: summary.pruefungNoetig, accent: summary.pruefungNoetig > 0 ? "text-status-partial" : undefined },
  ]
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {tiles.map((t) => (
        <div
          key={t.label}
          className="flex flex-col gap-0.5 rounded-lg border border-border bg-card px-3 py-2.5"
        >
          <dd className={cn("text-lg font-semibold leading-none text-foreground", t.accent)}>
            {t.value}
          </dd>
          <dt className="text-[11px] leading-tight text-muted-foreground">{t.label}</dt>
        </div>
      ))}
    </dl>
  )
}

// ---------------------------------------------------------------------------
// Approval / blocker panel
// ---------------------------------------------------------------------------
function ApprovalPanel({
  hasBlockers,
  breakdown,
  reasons,
  approvable,
  approved,
  busy,
  onApprove,
  onRecheck,
  onJumpToBlocker,
}: {
  hasBlockers: boolean
  breakdown: ReturnType<typeof blockerBreakdown>
  reasons: string[]
  approvable: boolean
  approved: boolean
  busy: boolean
  onApprove: () => void
  onRecheck: () => void
  onJumpToBlocker: () => void
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-lg border px-5 py-4",
        hasBlockers
          ? "border-destructive/30 bg-destructive/5"
          : "border-status-fulfilled/30 bg-status-fulfilled/5"
      )}
    >
      <div className="flex items-center gap-2">
        {hasBlockers ? (
          <AlertTriangle className="size-4 text-destructive" />
        ) : (
          <CheckCircle2 className="size-4 text-status-fulfilled" />
        )}
        <h2 className="text-sm font-semibold text-foreground">
          {hasBlockers ? "Freigabe blockiert" : "Bereit für Export"}
        </h2>
      </div>

      <p className="text-sm text-muted-foreground">
        {hasBlockers
          ? `Der Antrag kann noch nicht exportiert oder freigegeben werden, weil noch ${breakdown.blocker} Blocker zu klären ${
              breakdown.blocker === 1 ? "ist" : "sind"
            }.`
          : "Alle blockierenden Punkte sind geklärt. Prüfen Sie den Entwurf final und fahren Sie mit dem Export fort."}
      </p>

      {hasBlockers && (
        <ul className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
          <li>{breakdown.blocker} Blocker</li>
          <li>{breakdown.openMandatory} offene Pflichtfelder</li>
          <li>{breakdown.placeholderFields} Felder mit Platzhaltern</li>
          <li>{breakdown.missingEvidence} Belege fehlen</li>
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {hasBlockers && (
          <Button variant="outline" size="sm" onClick={onJumpToBlocker}>
            Zum ersten Blocker springen
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={onRecheck} disabled={busy}>
          <RefreshCw data-icon="inline-start" />
          Erneut prüfen
        </Button>
        {!hasBlockers && (
          <Button size="sm" render={<a href="/export" />} nativeButton={false}>
            Weiter zum Export
            <ArrowRight className="ml-1.5 size-3.5" />
          </Button>
        )}
        {/* Human-controlled approval — never auto-approves. */}
        <Button size="sm" onClick={onApprove} disabled={busy || !approvable}>
          <CheckCircle2 data-icon="inline-start" />
          Review freigeben
        </Button>
      </div>

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
// Quality-check group accordion
// ---------------------------------------------------------------------------
function GroupAccordion({
  group,
}: {
  group: ReturnType<typeof groupFindings>[number]
}) {
  const [open, setOpen] = React.useState(group.status !== "bestanden")
  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card">
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
        <span
          className={cn(
            "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium",
            GROUP_STATUS_STYLE[group.status]
          )}
        >
          {GROUP_STATUS_LABELS[group.status]}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-foreground">
            {group.label}
          </span>
          <span className="block truncate text-xs text-muted-foreground">
            {group.description}
          </span>
        </span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {group.findings.length === 0
            ? "Keine Befunde"
            : `${group.findings.length} Befund(e)`}
        </span>
      </button>
      {open && group.findings.length > 0 && (
        <ul className="flex flex-col gap-1 border-t border-border bg-muted/20 px-4 py-3">
          {dedupeFindings(group.findings).map((d) => {
            const blocker = d.findings.find((f) => f.severity === "blocker")
            const text = `${d.count > 1 ? `${d.count} × ` : ""}${d.description}`
            return (
              <li key={d.description} className="text-xs text-foreground">
                {blocker ? (
                  <button
                    type="button"
                    onClick={() =>
                      document
                        .getElementById(`blocker-${blocker.finding_id}`)
                        ?.scrollIntoView?.({ behavior: "smooth", block: "center" })
                    }
                    className="rounded text-left underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    • {text}
                  </button>
                ) : (
                  <>• {text}</>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Blocker card
// ---------------------------------------------------------------------------
function BlockerCard({
  finding,
  onRecheck,
}: {
  finding: ReviewFindingDto
  onRecheck: () => void
}) {
  const group = classifyFinding(finding)
  const isEvidence = group === "belege"
  return (
    <article
      id={`blocker-${finding.finding_id}`}
      className="flex flex-col gap-2 rounded-lg border border-border bg-card px-5 py-4"
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
            REVIEW_SEVERITY_STYLE.blocker
          )}
        >
          {REVIEW_SEVERITY_LABELS.blocker}
        </span>
        <h3 className="text-sm font-semibold text-foreground">
          {REVIEW_GROUP_LABELS[group]}
        </h3>
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="text-muted-foreground">Portal-Feld</dt>
        <dd className="text-foreground">{fieldLabel(finding.field_id)}</dd>
        <dt className="text-muted-foreground">Problem</dt>
        <dd className="text-foreground">
          {finding.description || REVIEW_FALLBACKS.title}
        </dd>
        <dt className="text-muted-foreground">Warum relevant</dt>
        <dd className="text-foreground">{blockerRelevance(finding)}</dd>
      </dl>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <Button variant="outline" size="xs" render={<a href="/editor" />} nativeButton={false}>
          Im Entwurf öffnen
        </Button>
        {finding.requirement_id && (
          <Button variant="ghost" size="xs" render={<a href="/anforderungen" />} nativeButton={false}>
            In Anforderungen öffnen
          </Button>
        )}
        {isEvidence && (
          <Button variant="ghost" size="xs" render={<a href="/quellen?tab=evidenz" />} nativeButton={false}>
            Evidenz prüfen
          </Button>
        )}
        <Button variant="ghost" size="xs" onClick={onRecheck}>
          Erneut prüfen
        </Button>
      </div>
    </article>
  )
}

// ---------------------------------------------------------------------------
// Deduplicated hint
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

function DedupedHint({ hint }: { hint: DedupedFinding }) {
  const [open, setOpen] = React.useState(false)
  return (
    <div className="rounded-md border border-border bg-card px-4 py-2.5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-foreground">
          {hint.count > 1 ? (
            <span className="font-medium">{hint.count} × </span>
          ) : null}
          {hint.description}
        </p>
        {hint.count > 1 && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="shrink-0 text-xs font-medium text-primary hover:underline"
          >
            Details anzeigen
          </button>
        )}
      </div>
      {open && hint.count > 1 && (
        <ul className="mt-2 flex flex-col gap-1 border-t border-border pt-2 text-xs text-muted-foreground">
          {hint.findings.map((f) => (
            <li key={f.finding_id}>• {fieldLabel(f.field_id)}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
