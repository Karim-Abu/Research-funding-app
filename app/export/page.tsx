"use client"

import * as React from "react"
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react"
import { useRouter } from "next/navigation"
import { AppShell } from "@/components/shell/app-shell"
import { ExportScreen } from "@/components/export/export-screen"
import { LiveExport, LiveExportSkeleton } from "@/components/export/live-export"
import { ActiveRunDetails } from "@/components/status/active-run-details"
import { useSession } from "@/components/providers/app-providers"
import { useActiveRun } from "@/components/providers/workflow-run-provider"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { PAGE_SCENARIOS, type PageScenario } from "@/lib/export-mock-data"
import {
  getRunFields,
  countOpenBlockers,
  ApiError,
  BRIDGE_UNREACHABLE_MESSAGE,
} from "@/lib/api"
import { getCurrentRunId, loadIntake } from "@/lib/intake-store"
import { cn } from "@/lib/utils"

// Set to true only during internal prototyping — never exposed in the Petra evaluation view.
const showDebugControls = false

function LiveExportContainer() {
  const router = useRouter()
  const { runId, source, loading } = useActiveRun()

  if (loading) {
    return (
      <div className="px-6 py-8">
        <LiveExportSkeleton />
      </div>
    )
  }
  if (!runId) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          Es liegt noch keine abgeschlossene Analyse vor. Starten Sie zunächst die
          Analyse.
        </p>
        <Button
          variant="outline"
          className="mt-4"
          onClick={() => router.push("/quellen")}
        >
          Zu den Quellen — Analyse starten
        </Button>
      </div>
    )
  }
  return (
    <div className="px-6 py-8">
      <LiveExport runId={runId} />
      <div className="mx-auto mt-6 max-w-5xl">
        <ActiveRunDetails runId={runId} source={source} />
      </div>
    </div>
  )
}

function MockExportBody() {
  const [scenario, setScenario] = React.useState<PageScenario>("default")
  const [showDebug, setShowDebug] = React.useState(false)
  const [blockerCount, setBlockerCount] = React.useState<number | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(() => {
    let cancelled = false
    setError(null)
    setBlockerCount(null)
    getRunFields(getCurrentRunId())
      .then((dto) => {
        if (!cancelled) setBlockerCount(countOpenBlockers(dto.issues))
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
  if (blockerCount === null) {
    return (
      <div className="flex flex-col gap-4 px-6 py-8">
        <Skeleton className="h-12 w-full rounded-md" />
        <div className="grid grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }
  return (
    <>
      <ExportScreen
        scenario={scenario}
        openBlockerCount={blockerCount}
        dataClass={loadIntake()?.vertraulichkeit || undefined}
      />
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

export default function ExportPage() {
  const { mode } = useSession()
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
    >
      {mode === "live" ? <LiveExportContainer /> : <MockExportBody />}
    </AppShell>
  )
}
