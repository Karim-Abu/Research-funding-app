"use client"

import * as React from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { AppShell } from "@/components/shell/app-shell"
import { DraftWorkspace } from "@/components/editor/draft-workspace"
import { LiveEditor } from "@/components/editor/live-editor"
import { Button } from "@/components/ui/button"
import { useSession } from "@/components/providers/app-providers"
import { useActiveRun } from "@/components/providers/workflow-run-provider"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"

function LiveEditorContainer() {
  const router = useRouter()
  // Deep link (?field=…) from Qualitätsprüfung/Export — parsed here (not in
  // LiveEditor) so component tests don't need a router mock.
  const searchParams = useSearchParams()
  const initialFieldId = searchParams.get("field")
  const { runId, loading } = useActiveRun()

  if (loading) return null
  if (!runId) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          Es liegt noch keine abgeschlossene Analyse vor. Starten Sie zunächst die
          Analyse, um Strukturvorlagen zu erzeugen.
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
  return <LiveEditor runId={runId} initialFieldId={initialFieldId} />
}

export default function EditorPage() {
  const { mode } = useSession()
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
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
