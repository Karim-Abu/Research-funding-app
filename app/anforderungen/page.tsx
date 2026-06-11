"use client"

import * as React from "react"
import { RefreshCw } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { RequirementsScreen } from "@/components/anforderungen/requirements-screen"
import { Button } from "@/components/ui/button"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
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

export default function AnforderungenPage() {
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
        // Distinct keys: state initializers must re-run once data arrives.
        <RequirementsScreen key="loading" forceState="loading" />
      ) : (
        <RequirementsScreen key="loaded" requirements={requirements} />
      )}
    </AppShell>
  )
}
