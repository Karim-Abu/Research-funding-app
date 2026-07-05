"use client"

import * as React from "react"
import { useSearchParams } from "next/navigation"
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
  "done",
  "current",
  "upcoming",
  "upcoming",
] as const

function LiveEditorContainer() {
  // Deep link (?field=…) from Qualitätsprüfung/Export — parsed here (not in
  // LiveEditor) so component tests don't need a router mock.
  const searchParams = useSearchParams()
  const initialFieldId = searchParams.get("field")
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
  return <LiveEditor runId={runId} initialFieldId={initialFieldId} />
}

export default function EditorPage() {
  const { mode } = useSession()
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={6}
      stepStatus={[...editorStepStatus]}
    >
      {mode === "live" ? (
        // useSearchParams requires a Suspense boundary in the App Router.
        <React.Suspense fallback={null}>
          <LiveEditorContainer />
        </React.Suspense>
      ) : (
        <DraftWorkspace />
      )}
    </AppShell>
  )
}
