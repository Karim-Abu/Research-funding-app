"use client"

import * as React from "react"
import { RefreshCw } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { PortalTransfer } from "@/components/portal-transfer/portal-transfer"
import { useSession } from "@/components/providers/app-providers"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { getActiveProjectId, getCurrentRunId, loadIntake } from "@/lib/intake-store"
import { listProjectRuns } from "@/lib/runs"
import { charCount, listFields, type PortalFieldDraftDto } from "@/lib/fields"
import { getReview, type ReviewPackageDto } from "@/lib/review"
import { getRunFields, ApiError, BRIDGE_UNREACHABLE_MESSAGE } from "@/lib/api"
import type { PortalFieldDraftDto as MockFieldDto } from "@/lib/backend-contract"
import type { StepStatus } from "@/lib/types"

const stepStatus: StepStatus[] = [
  "done",
  "done",
  "done",
  "done",
  "done",
  "done",
  "done",
  "current",
]

function isConfidential(): boolean {
  const v = loadIntake()?.vertraulichkeit
  return v === "internal" || v === "confidential"
}

/** Adapt the flat mock field shape to the live PortalFieldDraft DTO so the same
 * PortalTransfer component renders in mock mode. */
function adaptMockField(m: MockFieldDto): PortalFieldDraftDto {
  const count = charCount(m.text)
  return {
    draft_id: m.fieldId,
    field_id: m.fieldId,
    field_name: m.name,
    status: "needs_review",
    current_version: {
      draft_version_id: `${m.fieldId}-mock`,
      text: m.text,
      character_count: count,
      created_by: "template",
      created_at: new Date().toISOString(),
      content_hash: "",
    },
    character_count: count,
    character_limit: m.charLimit,
    open_issue_count: 0,
    evidence_links: [],
    open_issues: [],
  }
}

function emptyState(message: string) {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16 text-center">
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  )
}

function LivePortalTransfer({ runId }: { runId: string }) {
  const [fields, setFields] = React.useState<PortalFieldDraftDto[] | null>(null)
  const [review, setReview] = React.useState<ReviewPackageDto | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(() => {
    setError(null)
    setFields(null)
    listFields(runId)
      .then((f) => {
        setFields(f)
        // Review is best-effort context; missing review must not break the view.
        getReview(runId).then(setReview).catch(() => setReview(null))
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Feldtexte konnten nicht geladen werden.")
      )
  }, [runId])

  React.useEffect(() => load(), [load])

  if (error) {
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
  if (fields === null) {
    return (
      <div className="mx-auto flex max-w-4xl flex-col gap-4">
        <Skeleton className="h-8 w-48" />
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-40 w-full rounded-lg" />
        ))}
      </div>
    )
  }
  return (
    <PortalTransfer
      fields={fields}
      review={review}
      confidentialReminder={isConfidential()}
    />
  )
}

function LivePortalTransferContainer() {
  const [runId, setRunId] = React.useState<string | null>(null)
  const [resolved, setResolved] = React.useState(false)
  const [noProject, setNoProject] = React.useState(false)

  React.useEffect(() => {
    const projectId = getActiveProjectId()
    if (!projectId) {
      setNoProject(true)
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
      <div className="px-6 py-8">
        <Skeleton className="mx-auto h-40 max-w-4xl" />
      </div>
    )
  }
  if (noProject) return emptyState("Kein aktives Projekt ausgewählt.")
  if (!runId) return emptyState("Es liegt noch keine abgeschlossene Analyse vor.")
  return (
    <div className="px-6 py-8">
      <LivePortalTransfer runId={runId} />
    </div>
  )
}

function MockPortalTransfer() {
  const [fields, setFields] = React.useState<PortalFieldDraftDto[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(() => {
    setError(null)
    setFields(null)
    getRunFields(getCurrentRunId())
      .then((dto) => setFields(dto.fields.map(adaptMockField)))
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : BRIDGE_UNREACHABLE_MESSAGE)
      )
  }, [])

  React.useEffect(() => load(), [load])

  if (error) {
    return (
      <div className="px-6 py-10 text-center">
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button variant="outline" className="mt-4" onClick={load}>
          <RefreshCw data-icon="inline-start" />
          Erneut versuchen
        </Button>
      </div>
    )
  }
  if (fields === null) {
    return (
      <div className="px-6 py-8">
        <Skeleton className="mx-auto h-40 max-w-4xl" />
      </div>
    )
  }
  return (
    <div className="px-6 py-8">
      <PortalTransfer
        fields={fields}
        review={null}
        mockMode
        confidentialReminder={isConfidential()}
      />
    </div>
  )
}

export default function PortalTransferPage() {
  const { mode } = useSession()
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={8}
      stepStatus={stepStatus}
    >
      {mode === "live" ? <LivePortalTransferContainer /> : <MockPortalTransfer />}
    </AppShell>
  )
}
