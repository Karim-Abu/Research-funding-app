"use client"

import * as React from "react"
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { ReviewScreen } from "@/components/review/review-screen"
import { LiveReview } from "@/components/review/live-review"
import { useSession } from "@/components/providers/app-providers"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { PAGE_SCENARIOS, type PageScenario } from "@/lib/review-mock-data"
import {
  getRunFields,
  ApiError,
  BRIDGE_UNREACHABLE_MESSAGE,
} from "@/lib/api"
import { getActiveProjectId, getCurrentRunId, loadIntake } from "@/lib/intake-store"
import { listProjectRuns } from "@/lib/runs"
import type { RunFieldsDto } from "@/lib/backend-contract"
import { cn } from "@/lib/utils"
import type { StepStatus } from "@/lib/types"

const stepStatus: StepStatus[] = [
  "done",
  "done",
  "done",
  "done",
  "done",
  "done",
  "current",
  "upcoming",
]

// Set to true only during internal prototyping — never in the evaluation view.
const showDebugControls = false

function LiveReviewContainer() {
  const [runId, setRunId] = React.useState<string | null>(null)
  const [resolved, setResolved] = React.useState(false)

  React.useEffect(() => {
    const projectId = getActiveProjectId()
    if (!projectId) {
      setResolved(true)
      return
    }
    listProjectRuns(projectId)
      .then((runs) => setRunId(runs.find((r) => r.status === "completed")?.run_id ?? null))
      .catch(() => setRunId(null))
      .finally(() => setResolved(true))
  }, [])

  if (!resolved) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }
  if (!runId) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col items-center gap-4 px-6 py-16 text-center">
        <h1 className="text-xl font-semibold text-foreground">
          Noch keine Qualitätsprüfung durchgeführt
        </h1>
        <p className="text-sm text-muted-foreground">
          Starten Sie die Prüfung, um Pflichtfelder, Belege, Zeichenlimits und
          offene Punkte zu kontrollieren.
        </p>
        <p className="text-xs text-muted-foreground">
          Die automatische Prüfung wird verfügbar, sobald eine Analyse
          abgeschlossen ist.
        </p>
      </div>
    )
  }
  return (
    <div className="px-6 py-8">
      <LiveReview runId={runId} />
    </div>
  )
}

function MockReviewBody() {
  const [scenario, setScenario] = React.useState<PageScenario>("default")
  const [showDebug, setShowDebug] = React.useState(false)
  const [data, setData] = React.useState<RunFieldsDto | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(() => {
    let cancelled = false
    setError(null)
    setData(null)
    getRunFields(getCurrentRunId())
      .then((dto) => {
        if (!cancelled) setData(dto)
      })
      .catch((e) => {
        if (!cancelled)
          setError(e instanceof ApiError ? e.message : BRIDGE_UNREACHABLE_MESSAGE)
      })
    return () => {
      cancelled = true
    }
  }, [])

  React.useEffect(() => load(), [load])

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10">
        <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-16 text-center">
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button variant="outline" onClick={load}>
            <RefreshCw data-icon="inline-start" />
            Erneut versuchen
          </Button>
        </div>
      </div>
    )
  }
  if (data === null) {
    return (
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-8">
        <Skeleton className="h-8 w-40" />
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-14 w-full rounded-md" />
        ))}
      </div>
    )
  }
  return (
    <>
      <ReviewScreen
        key="loaded"
        scenario={scenario}
        initialData={data}
        dataClass={loadIntake()?.vertraulichkeit || undefined}
      />
      {/* Debug scenario switcher — hidden from normal user-facing UI */}
      {showDebugControls && (
        <div className="border-t border-border px-6 py-4">
          <button
            type="button"
            onClick={() => setShowDebug((v) => !v)}
            className={cn(
              "flex items-center gap-1.5 rounded text-xs font-medium text-muted-foreground",
              "outline-none transition-colors hover:text-foreground",
              "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            )}
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
              {PAGE_SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setScenario(s.id)}
                  className={cn(
                    "inline-flex h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    scenario === s.id
                      ? "border-foreground bg-foreground text-background"
                      : "border-border bg-card text-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  )
}

export default function ReviewPage() {
  const { mode } = useSession()
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={7}
      stepStatus={stepStatus}
    >
      {mode === "live" ? <LiveReviewContainer /> : <MockReviewBody />}
    </AppShell>
  )
}
