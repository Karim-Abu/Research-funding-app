"use client"

import * as React from "react"
import { RefreshCw } from "lucide-react"
import { useRouter } from "next/navigation"
import { AppShell } from "@/components/shell/app-shell"
import { PortalTransfer } from "@/components/portal-transfer/portal-transfer"
import { ActiveRunDetails } from "@/components/status/active-run-details"
import { useSession } from "@/components/providers/app-providers"
import { useActiveRun } from "@/components/providers/workflow-run-provider"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { getCurrentRunId, loadIntake } from "@/lib/intake-store"
import { getCapabilities } from "@/lib/capabilities"
import { charCount, listFields, type PortalFieldDraftDto } from "@/lib/fields"
import { listPortalFields, type PortalFieldInfoDto } from "@/lib/portal-fields"
import { getReview, type ReviewPackageDto } from "@/lib/review"
import { getRunFields, ApiError, BRIDGE_UNREACHABLE_MESSAGE } from "@/lib/api"
import type { PortalFieldDraftDto as MockFieldDto } from "@/lib/backend-contract"

function isConfidential(): boolean {
  const v = loadIntake()?.vertraulichkeit
  return v === "internal" || v === "confidential" || v === "nda"
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

function LivePortalTransfer({ runId }: { runId: string }) {
  const [fields, setFields] = React.useState<PortalFieldDraftDto[] | null>(null)
  const [review, setReview] = React.useState<ReviewPackageDto | null>(null)
  // Slice 4: full registry catalog for the "Alle Portalfelder" view.
  // Fail-open: on error the toggle is simply absent (today's view).
  const [portalFields, setPortalFields] = React.useState<
    PortalFieldInfoDto[] | null
  >(null)
  const [error, setError] = React.useState<string | null>(null)
  // Slice 3: whether copies are logged server-side. On a capabilities failure
  // we still attempt logging (the endpoint is active; errors go the fail-open
  // path) — only an explicit `false` disables the call.
  const [copyEventsEnabled, setCopyEventsEnabled] = React.useState(true)

  const load = React.useCallback(() => {
    setError(null)
    setFields(null)
    listFields(runId)
      .then((f) => {
        setFields(f)
        // Review is best-effort context; missing review must not break the view.
        getReview(runId).then(setReview).catch(() => setReview(null))
        listPortalFields(runId)
          .then(setPortalFields)
          .catch(() => setPortalFields(null))
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Feldtexte konnten nicht geladen werden.")
      )
  }, [runId])

  React.useEffect(() => load(), [load])
  React.useEffect(() => {
    getCapabilities()
      .then((caps) => setCopyEventsEnabled(caps.features.copy_events !== false))
      .catch(() => setCopyEventsEnabled(true))
  }, [])

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
      portalFields={portalFields}
      confidentialReminder={isConfidential()}
      runId={runId}
      copyEventsEnabled={copyEventsEnabled}
      onReload={load}
    />
  )
}

function LivePortalTransferContainer() {
  const router = useRouter()
  const { projectId, runId, source, loading } = useActiveRun()

  if (loading) {
    return (
      <div className="px-6 py-8">
        <Skeleton className="mx-auto h-40 max-w-4xl" />
      </div>
    )
  }
  if (!projectId) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          Kein aktives Projekt ausgewählt.
        </p>
        <Button
          variant="outline"
          className="mt-4"
          onClick={() => router.push("/")}
        >
          Zur Projektübersicht
        </Button>
      </div>
    )
  }
  if (!runId) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          Es liegt noch keine abgeschlossene Analyse vor.
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
      <LivePortalTransfer runId={runId} />
      <div className="mx-auto mt-6 max-w-4xl">
        <ActiveRunDetails runId={runId} source={source} />
      </div>
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
    >
      {mode === "live" ? <LivePortalTransferContainer /> : <MockPortalTransfer />}
    </AppShell>
  )
}
