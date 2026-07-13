"use client"

// Eine Run-Wahrheit für alle Screens: lädt Projekt, Runs, Partner und den
// kanonischen Review-Status einmal pro Seitenaufruf, wendet die Run-Auswahl-
// Ladder an (lib/active-run.ts) und leitet die Schrittstatus ab
// (lib/workflow.ts). Mock-Modus: inert — Mock-Bodies behalten ihre eigene
// Bridge (getCurrentRunId), der Stepper zeigt neutrale Statuswerte.

import * as React from "react"
import { useSession } from "@/components/providers/app-providers"
import {
  NO_ACTIVE_RUN,
  selectActiveRun,
  type ActiveRunSelection,
} from "@/lib/active-run"
import { getActiveProjectId, getSelectedRunId } from "@/lib/intake-store"
import { listPartners, type PartnerDto } from "@/lib/partners"
import { getProject, type ProjectDto } from "@/lib/projects"
import { listProjectRuns, type AnalysisRunDto } from "@/lib/runs"
import { getReviewStatus, type ReviewStatusDto } from "@/lib/status"
import {
  deriveStepStatuses,
  NEUTRAL_STEP_STATUSES,
  type StepUiStatus,
  type WorkflowStepId,
} from "@/lib/workflow"

interface WorkflowRunContextValue {
  projectId: string | null
  project: ProjectDto | null
  runs: AnalysisRunDto[]
  /** Aktiver Run gemäss Ladder — dieselbe ID auf allen Screens. */
  runId: string | null
  run: AnalysisRunDto | null
  source: ActiveRunSelection["source"]
  reviewStatus: ReviewStatusDto | null
  statuses: Record<WorkflowStepId, StepUiStatus>
  loading: boolean
  reload: () => void
}

const INERT_VALUE: WorkflowRunContextValue = {
  projectId: null,
  project: null,
  runs: [],
  runId: null,
  run: null,
  source: null,
  reviewStatus: null,
  statuses: NEUTRAL_STEP_STATUSES,
  loading: false,
  reload: () => {},
}

const WorkflowRunContext = React.createContext<WorkflowRunContextValue | null>(
  null
)

export function useActiveRun(): WorkflowRunContextValue {
  const ctx = React.useContext(WorkflowRunContext)
  if (!ctx) {
    throw new Error("useActiveRun must be used within <WorkflowRunProvider>")
  }
  return ctx
}

export function WorkflowRunProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const { mode } = useSession()
  const live = mode === "live"
  const [state, setState] = React.useState<
    Omit<WorkflowRunContextValue, "reload">
  >({ ...INERT_VALUE, loading: live })

  const reload = React.useCallback(() => {
    if (!live) {
      setState({ ...INERT_VALUE, loading: false })
      return
    }
    const projectId = getActiveProjectId()
    if (!projectId) {
      setState({ ...INERT_VALUE, loading: false })
      return
    }
    let cancelled = false
    setState((prev) => ({ ...prev, projectId, loading: true }))
    Promise.all([
      getProject(projectId).catch(() => null),
      listProjectRuns(projectId).catch(() => [] as AnalysisRunDto[]),
      listPartners(projectId).catch(() => null as PartnerDto[] | null),
    ]).then(async ([project, runs, partners]) => {
      if (cancelled) return
      const selection = selectActiveRun({
        projectActiveRunId: project?.active_run_id,
        userSelectedRunId: getSelectedRunId(),
        runs,
      })
      const reviewStatus = selection.runId
        ? await getReviewStatus(selection.runId).catch(() => null)
        : null
      if (cancelled) return
      setState({
        projectId,
        project,
        runs,
        runId: selection.runId,
        run: selection.run,
        source: selection.source,
        reviewStatus,
        statuses: deriveStepStatuses({
          project,
          runs,
          activeRun: selection,
          reviewStatus,
          partners,
        }),
        loading: false,
      })
    })
    return () => {
      cancelled = true
    }
  }, [live])

  React.useEffect(() => reload(), [reload])

  const value = React.useMemo<WorkflowRunContextValue>(
    () => ({ ...state, reload }),
    [state, reload]
  )

  return (
    <WorkflowRunContext.Provider value={value}>
      {children}
    </WorkflowRunContext.Provider>
  )
}
