"use client"

import * as React from "react"
import { RefreshCw } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { RequirementsScreen } from "@/components/anforderungen/requirements-screen"
import { LiveRequirements } from "@/components/anforderungen/live-requirements"
import { Button } from "@/components/ui/button"
import { useSession } from "@/components/providers/app-providers"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { getActiveProjectId } from "@/lib/intake-store"
import { listProjectRuns } from "@/lib/runs"
import {
  getProjectState,
  ApiError,
  BRIDGE_UNREACHABLE_MESSAGE,
} from "@/lib/api"
import type { Requirement } from "@/lib/anforderungen-mock-data"

const stepStatus = [
  "done",
  "done",
  "current",
  "upcoming",
  "upcoming",
  "upcoming",
  "upcoming",
  "upcoming",
] as const

// --- Live mode: render the run-scoped RequirementAssessments ----------------
function LiveAnforderungen() {
  const [runId, setRunId] = React.useState<string | null>(null)
  const [resolved, setResolved] = React.useState(false)

  React.useEffect(() => {
    const projectId = getActiveProjectId()
    if (!projectId) {
      setResolved(true)
      return
    }
    listProjectRuns(projectId)
      .then((runs) => {
        const completed = runs.find((r) => r.status === "completed")
        setRunId(completed?.run_id ?? null)
      })
      .catch(() => setRunId(null))
      .finally(() => setResolved(true))
  }, [])

  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={3}
      stepStatus={[...stepStatus]}
    >
      {!resolved ? null : runId ? (
        <LiveRequirements runId={runId} />
      ) : (
        <div className="mx-auto max-w-3xl px-6 py-16 text-center">
          <p className="text-sm text-muted-foreground">
            Es liegt noch keine abgeschlossene Prüfung vor. Starten Sie zunächst
            unter «Quellen» eine Analyse.
          </p>
        </div>
      )}
    </AppShell>
  )
}

// --- Mock mode: unchanged elaborate mock screen -----------------------------
function MockAnforderungen() {
  const [requirements, setRequirements] = React.useState<Requirement[] | null>(
    null
  )
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(() => {
    let cancelled = false
    setError(null)
    setRequirements(null)
    getProjectState(activeProjectId)
      .then((state) => {
        if (!cancelled) setRequirements(state.requirements)
      })
      .catch((e) => {
        if (!cancelled)
          setError(
            e instanceof ApiError ? e.message : BRIDGE_UNREACHABLE_MESSAGE
          )
      })
    return () => {
      cancelled = true
    }
  }, [])

  React.useEffect(() => load(), [load])

  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={3}
      stepStatus={[...stepStatus]}
    >
      {error ? (
        <div className="mx-auto max-w-4xl px-6 py-10">
          <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-16 text-center">
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button variant="outline" onClick={load}>
              <RefreshCw data-icon="inline-start" />
              Erneut versuchen
            </Button>
          </div>
        </div>
      ) : requirements === null ? (
        <RequirementsScreen key="loading" forceState="loading" />
      ) : (
        <RequirementsScreen key="loaded" requirements={requirements} />
      )}
    </AppShell>
  )
}

export default function AnforderungenPage() {
  const { mode } = useSession()
  return mode === "live" ? <LiveAnforderungen /> : <MockAnforderungen />
}
