"use client"

import * as React from "react"
import { RefreshCw, CheckCircle2, ChevronDown, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  getReview,
  startRecheck,
  createApproval,
  ReviewError,
  APPROVAL_STATUS_LABELS,
  APPROVAL_STATUS_VARIANT,
  type ReviewPackageDto,
} from "@/lib/review"

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
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-48" />
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  const reasons = disabledReasons(pkg)
  const approvable = reasons.length === 0 && pkg.approval_status !== "approved"
  const blockerFindings = pkg.findings.filter((f) => f.severity === "blocker")
  const warningFindings = pkg.findings.filter((f) => f.severity === "warning")

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-lg font-semibold">Qualitätsprüfung</h1>
        <Badge variant={APPROVAL_STATUS_VARIANT[pkg.approval_status] ?? "secondary"}>
          {APPROVAL_STATUS_LABELS[pkg.approval_status] ?? "Status unbekannt"}
        </Badge>
      </div>

      <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
        <span>{pkg.blocker_count} Blocker</span>
        <span>{pkg.warning_count} Hinweise</span>
      </div>

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

      {pkg.recheck_required && (
        <p
          role="status"
          className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900"
        >
          Es liegen ungeprüfte Änderungen vor. Bitte führen Sie eine erneute Prüfung
          durch, bevor Sie freigeben.
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

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={recheck} disabled={busy}>
          <RefreshCw data-icon="inline-start" />
          Erneut prüfen
        </Button>
        <Button onClick={approve} disabled={busy || !approvable}>
          <CheckCircle2 data-icon="inline-start" />
          Review freigeben
        </Button>
      </div>
      {!approvable && pkg.approval_status !== "approved" && (
        <ul className="text-xs text-muted-foreground">
          {reasons.map((r) => (
            <li key={r}>• {r}</li>
          ))}
        </ul>
      )}

      {blockerFindings.length > 0 && (
        <FindingList title="Blocker" findings={blockerFindings} tone="destructive" />
      )}
      {warningFindings.length > 0 && (
        <FindingList title="Hinweise" findings={warningFindings} tone="outline" />
      )}
    </div>
  )
}

function FindingList({
  title,
  findings,
  tone,
}: {
  title: string
  findings: { finding_id: string; description: string }[]
  tone: "destructive" | "outline"
}) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold">{title}</h2>
      <ul className="flex flex-col gap-1">
        {findings.map((f) => (
          <li
            key={f.finding_id}
            className="flex items-start gap-2 rounded border border-border px-2 py-1 text-xs"
          >
            <Badge variant={tone} className="mt-0.5">
              {title === "Blocker" ? "Blocker" : "Hinweis"}
            </Badge>
            <span>{f.description}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
