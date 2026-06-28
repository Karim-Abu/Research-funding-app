"use client"

import * as React from "react"
import { AppShell } from "@/components/shell/app-shell"
import { DraftWorkspace } from "@/components/editor/draft-workspace"
import { LiveEditor } from "@/components/editor/live-editor"
import { useSession } from "@/components/providers/app-providers"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { getActiveProjectId } from "@/lib/intake-store"
import { listProjectRuns } from "@/lib/runs"

const editorStepStatus = [
  "done",
  "done",
  "done",
  "done",
  "current",
  "upcoming",
  "upcoming",
] as const

function LiveEditorContainer() {
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

  if (!resolved) return null
  if (!runId) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          Es liegt noch keine abgeschlossene Analyse vor. Starten Sie zunächst die
          Analyse, um Strukturvorlagen zu erzeugen.
        </p>
      </div>
    )
  }
  return <LiveEditor runId={runId} />
}

export default function EditorPage() {
  const { mode } = useSession()
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={5}
      stepStatus={[...editorStepStatus]}
    >
      {mode === "live" ? <LiveEditorContainer /> : <DraftWorkspace />}
    </AppShell>
  )
}
