"use client"

import * as React from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Play, ChevronDown, ChevronRight, XCircle } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { AnalyseEinstellungenDialog } from "@/components/run/analyse-einstellungen-dialog"
import { SourceTable } from "@/components/quellen/source-table"
import { PublicResearchPanel } from "@/components/quellen/public-research-panel"
import { MarketComparisonSection } from "@/components/quellen/market-comparison-section"
import { EvidenceTab } from "@/components/quellen/evidence-tab"
import {
  AnalysisProgressBanner,
  StoppedAnalysisBanner,
  CompletedAnalysisBanner,
  LocalOnlyBanner,
} from "@/components/quellen/analysis-progress-banner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import {
  dummySources,
  dummyEvidence,
  dummyAnalysisSteps,
  URL_SOURCE_KIND_LABELS,
  type AnalysisProgressStep,
  type PageAnalysisState,
  type Source,
  type UrlSourceKind,
} from "@/lib/quellen-mock-data"
import {
  startRun as startLegacyRun,
  getRun as getLegacyRun,
  stopRun as stopLegacyRun,
  resumeRun as resumeLegacyRun,
  ApiError,
  BRIDGE_UNREACHABLE_MESSAGE,
  type RunCostDto,
  type RunStartRequestDto,
} from "@/lib/api"
import { loadIntake, setCurrentRunId, getActiveProjectId } from "@/lib/intake-store"
import { DataClassBadge } from "@/components/status/data-class-badge"
import {
  isCloudAllowed,
  mostRestrictiveDataClass,
  type AnalyseSettings,
  type DataClass,
  type IntakeFormData,
  type Role,
} from "@/lib/types"
import { useSession } from "@/components/providers/app-providers"
import {
  listSources,
  uploadFiles,
  createTextSource,
  createUrlSource,
  deleteSource,
  type SourceDocumentDto,
} from "@/lib/sources"
import { getCapabilities, type Capabilities } from "@/lib/capabilities"
import {
  cancelRun,
  createRun,
  listProjectRuns,
  RunError,
  type RunSettings,
} from "@/lib/runs"
import { createProcessingConfirmation } from "@/lib/processing-confirmations"
import { pollOperation, type PollHandle } from "@/lib/operations"
import { LiveEvidence } from "@/components/quellen/live-evidence"
import { dataClassificationFromFlat } from "@/lib/data-classification"

// Map a live contract SourceDocument onto the existing table row shape.
const SOURCE_TYPE_LABEL: Record<string, Source["type"]> = {
  pdf: "PDF",
  docx: "DOCX",
  txt: "Text",
  url: "URL",
}

function toSourceRow(s: SourceDocumentDto): Source {
  let errorHint: string | undefined
  if (s.status === "failed") {
    errorHint =
      s.error_message ??
      "Die Quelle konnte nicht verarbeitet werden. Bitte Format prüfen, erneut hochladen oder entfernen."
  } else if (s.status === "needs_manual_input") {
    errorHint =
      "Kein durchsuchbarer Text gefunden. Bitte Datei prüfen oder Inhalt als Text erfassen."
  }
  return {
    id: s.source_id,
    name: s.name,
    type: SOURCE_TYPE_LABEL[s.type] ?? "Text",
    status: s.status,
    addedBy: "Projektteam",
    addedAt: s.created_at
      ? new Date(s.created_at).toLocaleString("de-CH")
      : "Unbekannt",
    errorHint,
  }
}

function isLocalSourceId(id: string): boolean {
  return id.startsWith("local-source-")
}

function localSourceId(kind: string): string {
  return `local-source-${kind}-${Date.now()}-${Math.random()
    .toString(16)
    .slice(2)}`
}

// ---------------------------------------------------------------------------
// Scenario types (dialog demo only — collapsed by default)
// ---------------------------------------------------------------------------
type EstimateState = "ready" | "loading" | "unavailable"

interface DialogScenario {
  id: string
  label: string
  role: Role
  dataClass: DataClass
  kiAvailable: boolean
  webAvailable: boolean
  hasActiveRun: boolean
  estimateState: EstimateState
  variant: "full" | "compact"
}

const DIALOG_SCENARIOS: DialogScenario[] = [
  {
    id: "standard",
    label: "Standard",
    role: "lead_admin",
    dataClass: "public",
    kiAvailable: true,
    webAvailable: true,
    hasActiveRun: false,
    estimateState: "ready",
    variant: "full",
  },
  {
    id: "member",
    label: "Mitglied",
    role: "member",
    dataClass: "public",
    kiAvailable: true,
    webAvailable: true,
    hasActiveRun: false,
    estimateState: "ready",
    variant: "full",
  },
  {
    id: "internal",
    label: "Intern",
    role: "lead_admin",
    dataClass: "internal",
    kiAvailable: true,
    webAvailable: true,
    hasActiveRun: false,
    estimateState: "ready",
    variant: "full",
  },
  {
    id: "confidential",
    label: "Vertraulich",
    role: "lead_admin",
    dataClass: "confidential",
    kiAvailable: true,
    webAvailable: true,
    hasActiveRun: false,
    estimateState: "ready",
    variant: "full",
  },
  {
    id: "active-run",
    label: "Durchlauf läuft",
    role: "lead_admin",
    dataClass: "public",
    kiAvailable: true,
    webAvailable: true,
    hasActiveRun: true,
    estimateState: "ready",
    variant: "full",
  },
  {
    id: "estimate-loading",
    label: "Schätzung lädt",
    role: "lead_admin",
    dataClass: "public",
    kiAvailable: true,
    webAvailable: true,
    hasActiveRun: false,
    estimateState: "loading",
    variant: "full",
  },
  {
    id: "estimate-unavailable",
    label: "Schätzung nicht verfügbar",
    role: "lead_admin",
    dataClass: "public",
    kiAvailable: true,
    webAvailable: true,
    hasActiveRun: false,
    estimateState: "unavailable",
    variant: "full",
  },
  {
    id: "compact",
    label: "Kompaktansicht",
    role: "lead_admin",
    dataClass: "public",
    kiAvailable: true,
    webAvailable: true,
    hasActiveRun: false,
    estimateState: "ready",
    variant: "compact",
  },
]

// ---------------------------------------------------------------------------
// Step status
// ---------------------------------------------------------------------------

const quellenStepStatus = [
  "done",
  "current",
  "upcoming",
  "upcoming",
  "upcoming",
  "upcoming",
  "upcoming",
] as const

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

// Set to true only during internal prototyping — never in the evaluation view.
const SHOW_DEBUG_CONTROLS = false

function liveAnalysisSteps(progressPercent: number): AnalysisProgressStep[] {
  const progress = Math.max(0, Math.min(100, progressPercent))
  const labels = [
    "Quellen werden gesichert",
    "Anforderungen werden geprueft",
    "Belege werden verknuepft",
    "Ergebnisse werden gespeichert",
  ]
  const thresholds = [10, 35, 70, 95]
  const currentIndex = thresholds.findIndex((threshold) => progress < threshold)
  const activeIndex = currentIndex === -1 ? labels.length - 1 : currentIndex
  return labels.map((label, index) => ({
    id: `live-${index + 1}`,
    label,
    state:
      progress >= 100 || index < activeIndex
        ? "done"
        : index === activeIndex
          ? "running"
          : "pending",
  }))
}

export default function QuellenPage() {
  // useSearchParams requires a Suspense boundary in the App Router.
  return (
    <React.Suspense fallback={null}>
      <QuellenPageContent />
    </React.Suspense>
  )
}

type QuellenTab = "quellen" | "evidenz"

function QuellenPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const tabFromUrl: QuellenTab =
    searchParams.get("tab") === "evidenz" ? "evidenz" : "quellen"
  // Deep link from Anforderungen ("Beleg ansehen"): focus one evidence card.
  const focusAnchorId = searchParams.get("anchor")

  const [activeTab, setActiveTab] = React.useState<QuellenTab>(tabFromUrl)
  // Evidence → source navigation: switch tab + open that source's details.
  const [sourceDetailId, setSourceDetailId] = React.useState<string | null>(null)
  // Stepper deep links (step 2 -> Quellen, step 4 -> Evidenz) navigate within
  // this route, so follow URL changes after mount as well.
  React.useEffect(() => {
    setActiveTab(tabFromUrl)
  }, [tabFromUrl])

  function handleTabChange(value: unknown) {
    const tab: QuellenTab = value === "evidenz" ? "evidenz" : "quellen"
    setActiveTab(tab)
    router.replace(tab === "evidenz" ? "/quellen?tab=evidenz" : "/quellen", {
      scroll: false,
    })
  }

  function handleOpenSourceFromEvidence(sourceId: string) {
    handleTabChange("quellen")
    setSourceDetailId(sourceId)
  }

  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [activeScenario, setActiveScenario] = React.useState<DialogScenario>(
    DIALOG_SCENARIOS[0]
  )
  const [analysisState, setAnalysisState] =
    React.useState<PageAnalysisState>("idle")
  const [analysisSteps, setAnalysisSteps] =
    React.useState<AnalysisProgressStep[]>(dummyAnalysisSteps)
  const [runCost, setRunCost] = React.useState<RunCostDto | undefined>(undefined)
  const [canResume, setCanResume] = React.useState(false)
  const [apiError, setApiError] = React.useState<string | null>(null)
  const [showDebugControls, setShowDebugControls] = React.useState(false)

  // Intake aus der Session: undefined = noch nicht geladen (Hydration),
  // null = fehlt -> Warn-Banner + Start gesperrt.
  const [intake, setIntake] = React.useState<IntakeFormData | null | undefined>(
    undefined
  )
  React.useEffect(() => {
    setIntake(loadIntake())
  }, [])
  // Vom Backend gemeldete effektive Klasse hat Vorrang vor dem Intake-Wert.
  const [backendDataClass, setBackendDataClass] =
    React.useState<DataClass | null>(null)

  // Beta: Quellen tragen noch keine eigene Datenklasse — effektiv ist die
  // restriktivste aus dem Projektkontext (derzeit nur das Intake).
  const effectiveDataClass: DataClass | null =
    backendDataClass ??
    (intake
      ? mostRestrictiveDataClass([intake.vertraulichkeit || "public"])
      : null)

  // Run lifecycle: the page only starts a run and polls its status via the
  // API layer; the progression itself lives behind lib/api.ts (mock or bridge).
  const runIdRef = React.useRef<string | null>(null)
  const operationPollRef = React.useRef<PollHandle | null>(null)
  const pollTimer = React.useRef<ReturnType<typeof setInterval> | undefined>(
    undefined
  )
  React.useEffect(
    () => () => {
      clearInterval(pollTimer.current)
      operationPollRef.current?.stop()
    },
    []
  )

  const stopPolling = React.useCallback(() => {
    clearInterval(pollTimer.current)
    pollTimer.current = undefined
    operationPollRef.current?.stop()
    operationPollRef.current = null
  }, [])

  const startPolling = React.useCallback(() => {
    stopPolling()
    pollTimer.current = setInterval(async () => {
      const runId = runIdRef.current
      if (!runId) return
      try {
        const dto = await getLegacyRun(runId)
        if (dto.steps) setAnalysisSteps(dto.steps)
        setRunCost(dto.cost)
        setCanResume(dto.canResume ?? false)
        if (dto.effectiveDataClass) setBackendDataClass(dto.effectiveDataClass)
        if (dto.status === "completed" || dto.status === "paused_for_review") {
          // paused_for_review = Analyse fertig, wartet auf die menschliche Prüfung.
          stopPolling()
          setAnalysisState("completed")
        } else if (
          dto.status === "stopped" ||
          dto.status === "failed" ||
          dto.status === "cancelled"
        ) {
          // Backend-initiated stop (e.g. cost limit reached) / cancellation.
          stopPolling()
          setAnalysisState("stopped")
        }
        // "created" und "running" -> weiter pollen.
      } catch (e) {
        stopPolling()
        setAnalysisState("idle")
        setApiError(
          e instanceof ApiError ? e.message : BRIDGE_UNREACHABLE_MESSAGE
        )
      }
    }, 1000)
  }, [stopPolling])

  // Die effektive Datenklasse steuert Banner und Dialog; das Demo-Szenario
  // greift nur, solange kein Intake vorliegt (Debug-Pfad).
  const dialogDataClass = effectiveDataClass ?? activeScenario.dataClass
  const isLocalOnly = !isCloudAllowed(dialogDataClass)

  function openDialogWith(scenario: DialogScenario) {
    setActiveScenario(scenario)
    setDialogOpen(true)
  }

  async function handleAnalysisStart(settings: AnalyseSettings) {
    if (!intake || !effectiveDataClass) return
    if (liveMode && !projectId) {
      setApiError("Kein aktives Projekt ausgewaehlt.")
      return
    }
    setDialogOpen(false)
    setApiError(null)
    stopPolling()
    setAnalysisSteps(
      liveMode
        ? liveAnalysisSteps(1)
        : dummyAnalysisSteps.map((s, i) => ({
            ...s,
            state: i === 0 ? ("running" as const) : ("pending" as const),
          }))
    )
    setAnalysisState("running")
    setCanResume(false)
    setRunCost(undefined)
    try {
      if (liveMode && projectId) {
        // Derive the processing mode from the run-settings opt-in. Cloud-KI is
        // only used when the user enabled it AND explicitly confirmed for a
        // public/synthetic project; otherwise the run stays deterministic.
        const processedVersionIds = liveSources
          .filter((s) => s.status === "processed" && s.current_source_version_id)
          .map((s) => s.current_source_version_id as string)
        const useCloud =
          settings.ki &&
          settings.cloudConfirmed === true &&
          !isLocalOnly &&
          processedVersionIds.length > 0

        let runSettings: RunSettings = {
          processing_mode: "deterministic_only",
          max_cost_chf: settings.costLimit,
          max_llm_calls: 0,
          max_web_calls: 0,
        }
        if (useCloud) {
          const confirmation = await createProcessingConfirmation(
            projectId,
            processedVersionIds
          )
          runSettings = {
            processing_mode: "cloud_assisted",
            max_cost_chf: settings.costLimit,
            max_llm_calls: 25,
            max_web_calls: 0,
            source_version_ids: processedVersionIds,
            internal_cloud_confirmation_id: confirmation.confirmation_id,
          }
        }
        const accepted = await createRun(projectId, runSettings)
        runIdRef.current = accepted.resource_id
        setCurrentRunId(accepted.resource_id)
        operationPollRef.current = pollOperation(accepted.operation_id, {
          intervalMs: (capabilities?.polling_interval_seconds ?? 1) * 1000,
          onUpdate: (operation) => {
            setAnalysisSteps(liveAnalysisSteps(operation.progress_percent ?? 25))
          },
          onTerminal: (operation) => {
            operationPollRef.current = null
            if (operation.status === "succeeded") {
              setAnalysisSteps(liveAnalysisSteps(100))
              setCompletedRunId(operation.resource_id)
              setAnalysisState("completed")
              void refreshSources()
              return
            }
            setCanResume(false)
            setAnalysisState("stopped")
            if (operation.status === "failed") {
              setApiError(
                operation.error?.detail ??
                  "Die Analyse konnte nicht abgeschlossen werden."
              )
            }
          },
        })
        return
      }
      const startRequest: RunStartRequestDto = {
        intake,
        settings,
        effectiveDataClass,
      }
      const { runId } = await startLegacyRun(startRequest)
      runIdRef.current = runId
      setCurrentRunId(runId)
      startPolling()
    } catch (e) {
      setAnalysisState("idle")
      if (e instanceof RunError || e instanceof ApiError) {
        setApiError(e.message)
      } else {
        setApiError(BRIDGE_UNREACHABLE_MESSAGE)
      }
    }
  }

  function handleAnalysisStop() {
    stopPolling()
    setAnalysisState("stopped")
    const runId = runIdRef.current
    if (!runId) return
    if (liveMode) {
      setCanResume(false)
      void cancelRun(runId).catch(() => undefined)
      return
    }
    // Refresh canResume/cost once from the stopped run.
    void stopLegacyRun(runId)
      .then(() => getLegacyRun(runId))
      .then((dto) => {
        setCanResume(dto.canResume ?? false)
        setRunCost(dto.cost)
      })
      .catch(() => setCanResume(false))
  }

  function handleAnalysisResume() {
    const runId = runIdRef.current
    if (!runId) return
    if (liveMode) {
      setCanResume(false)
      setAnalysisState("stopped")
      return
    }
    setAnalysisState("running")
    resumeLegacyRun(runId)
      .then(startPolling)
      .catch((e) => {
        setAnalysisState("stopped")
        setApiError(
          e instanceof ApiError ? e.message : BRIDGE_UNREACHABLE_MESSAGE
        )
      })
  }

  // --- Live sources (Milestone 2) --------------------------------------------
  const { mode } = useSession()
  const liveMode = mode === "live"
  const [projectId, setProjectId] = React.useState<string | null>(null)
  const [liveSources, setLiveSources] = React.useState<SourceDocumentDto[]>([])
  const [localSourceRows, setLocalSourceRows] = React.useState<Source[]>([])
  const [completedRunId, setCompletedRunId] = React.useState<string | null>(null)
  const [capabilities, setCapabilities] = React.useState<Capabilities | null>(
    null
  )

  React.useEffect(() => {
    if (!liveMode) return
    setProjectId(getActiveProjectId())
    void getCapabilities().then(setCapabilities)
  }, [liveMode])

  React.useEffect(() => {
    if (!liveMode) setLocalSourceRows([])
  }, [liveMode])

  const refreshSources = React.useCallback(async () => {
    if (!liveMode || !projectId) return
    try {
      setLiveSources(await listSources(projectId))
    } catch {
      // keep the last known list on transient errors
    }
  }, [liveMode, projectId])

  React.useEffect(() => {
    void refreshSources()
  }, [refreshSources])

  // Poll while any source is still being processed.
  React.useEffect(() => {
    if (!liveMode || !projectId) return
    const pending = liveSources.some(
      (s) => s.status === "uploaded" || s.status === "processing"
    )
    if (!pending) return
    const ms = (capabilities?.polling_interval_seconds ?? 2) * 1000
    const timer = setInterval(() => void refreshSources(), ms)
    return () => clearInterval(timer)
  }, [liveMode, projectId, liveSources, capabilities, refreshSources])

  const sourceClassification = React.useMemo(
    () => dataClassificationFromFlat(effectiveDataClass ?? "public"),
    [effectiveDataClass]
  )

  const handleUploadSources = React.useCallback(
    async (files: File[]) => {
      if (!projectId) throw new Error("Kein aktives Projekt ausgewählt.")
      await uploadFiles(projectId, files, sourceClassification)
      await refreshSources()
    },
    [projectId, sourceClassification, refreshSources]
  )

  const handleDeleteSource = React.useCallback(
    (id: string) => {
      if (isLocalSourceId(id)) {
        setLocalSourceRows((prev) => prev.filter((source) => source.id !== id))
        return
      }
      void deleteSource(id).then(refreshSources).catch(() => undefined)
    },
    [refreshSources]
  )

  const handleAddTextSource = React.useCallback(
    async ({ title, text }: { title: string; text: string }) => {
      if (!projectId) throw new Error("Kein aktives Projekt ausgewählt.")
      await createTextSource(projectId, title, text, sourceClassification)
      await refreshSources()
    },
    [projectId, sourceClassification, refreshSources]
  )

  const handleAddUrlSource = React.useCallback(
    async ({ url, kind }: { url: string; kind: UrlSourceKind }) => {
      if (!projectId) throw new Error("Kein aktives Projekt ausgewählt.")
      const canUseBackendUrlImport = Boolean(
        capabilities?.features?.url_import ||
          capabilities?.supported_source_types.includes("url")
      )

      if (canUseBackendUrlImport) {
        try {
          await createUrlSource(
            projectId,
            url,
            `${URL_SOURCE_KIND_LABELS[kind]}: ${url}`,
            sourceClassification
          )
          await refreshSources()
          return
        } catch {
          // Fall back to a transparent frontend row when the beta deployment
          // still reports URL import as unavailable.
        }
      }

      setLocalSourceRows((prev) => [
        {
          id: localSourceId("url"),
          name: url,
          type: "URL",
          status: "uploaded",
          addedBy: currentUser.name,
          addedAt: "soeben",
          note: `${URL_SOURCE_KIND_LABELS[kind]} · Verarbeitung ausstehend.`,
        },
        ...prev,
      ])
    },
    [capabilities, projectId, refreshSources, sourceClassification]
  )

  const handleImportSources = React.useCallback(
    ({
      project,
      sources,
    }: {
      project: { title: string }
      sources: Source[]
    }) => {
      setLocalSourceRows((prev) => [
        ...sources.map((source) => ({
          ...source,
          id: localSourceId("import"),
          type: "Übernommen" as const,
          status: "uploaded" as const,
          addedBy: currentUser.name,
          addedAt: "soeben",
          note: `Aus „${project.title}“ übernommen. Verarbeitung ausstehend.`,
        })),
        ...prev,
      ])
    },
    []
  )

  // Resolve the latest completed run so the Evidenz tab can show live evidence.
  React.useEffect(() => {
    if (!liveMode || !projectId) {
      setCompletedRunId(null)
      return
    }
    let cancelled = false
    listProjectRuns(projectId)
      .then((runs) => {
        if (cancelled) return
        const completed = runs.find((r) => r.status === "completed")
        setCompletedRunId(completed?.run_id ?? null)
      })
      .catch(() => {
        if (!cancelled) setCompletedRunId(null)
      })
    return () => {
      cancelled = true
    }
  }, [liveMode, projectId, liveSources])

  const sourceRows: Source[] = liveMode
    ? [...localSourceRows, ...liveSources.map(toSourceRow)]
    : dummySources
  const sourceCount = sourceRows.length
  const evidenceCount = dummyEvidence.length

  // STEP 12: the live "Analyse starten" action stays disabled until the server
  // capability (features.runs) enables it (Milestone 4). Mock mode is unaffected.
  const runsEnabled = !liveMode || Boolean(capabilities?.features?.runs)

  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={2}
      stepStatus={[...quellenStepStatus]}
    >
      <div className="mx-auto max-w-5xl px-6 py-8">

        {/* Page header */}
        <div className="mb-6 flex items-start justify-between gap-4">
          <div className="flex flex-col gap-2">
            <h1 className="text-balance text-2xl font-semibold text-foreground">
              Quellen &amp; Evidenz
            </h1>
            <p className="text-sm text-muted-foreground">
              Laden Sie Unterlagen hoch. Die Plattform erkennt daraus Anforderungen und passende Belege.
            </p>
            {effectiveDataClass && (
              <DataClassBadge dataClass={effectiveDataClass} />
            )}
          </div>

          {/* Primary action — only shown when no analysis is running */}
          {analysisState !== "running" && (
            <div className="flex shrink-0 flex-col items-end gap-1">
              <Button
                onClick={() => openDialogWith(DIALOG_SCENARIOS[0])}
                disabled={!intake || !runsEnabled}
              >
                <Play className="mr-1.5 size-4" />
                {analysisState === "completed"
                  ? "Analyse erneut starten"
                  : "Analyse starten"}
              </Button>
              {liveMode && !runsEnabled && (
                <span className="text-xs text-muted-foreground">
                  Die Analyse wird in einer späteren Version verfügbar.
                </span>
              )}
            </div>
          )}
        </div>

        {/* Missing intake — run start requires project data */}
        {intake === null && (
          <div
            role="alert"
            className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-status-partial/40 bg-status-partial/8 px-4 py-3"
          >
            <p className="text-sm text-foreground">
              Noch keine Projektangaben vorhanden — bitte füllen Sie zuerst das
              Intake aus.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push("/intake")}
            >
              Zum Intake
            </Button>
          </div>
        )}

        {/* Confidentiality banner */}
        {isLocalOnly && <div className="mb-4"><LocalOnlyBanner /></div>}

        {/* API error banner (German message from the error envelope) */}
        {apiError && (
          <div
            role="alert"
            className="mb-4 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-foreground"
          >
            <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
            {apiError}
          </div>
        )}

        {/* Analysis state banners */}
        {analysisState === "running" && (
          <div className="mb-4">
            <AnalysisProgressBanner
              steps={analysisSteps}
              cost={runCost}
              onStop={handleAnalysisStop}
            />
          </div>
        )}
        {analysisState === "stopped" && (
          <div className="mb-4">
            <StoppedAnalysisBanner
              canResume={canResume}
              onResume={handleAnalysisResume}
            />
          </div>
        )}
        {analysisState === "completed" && (
          <div className="mb-4">
            <CompletedAnalysisBanner
              onGoToRequirements={() => router.push("/anforderungen")}
              onShowEvidence={() => handleTabChange("evidenz")}
            />
          </div>
        )}

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList className="mb-6">
            <TabsTrigger value="quellen">
              Quellen ({sourceCount})
            </TabsTrigger>
            <TabsTrigger value="evidenz">
              {liveMode ? "Evidenz" : `Evidenz (${evidenceCount})`}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="quellen">
            {liveMode ? (
              <div className="flex flex-col gap-6">
                {!projectId && (
                  <p
                    role="alert"
                    className="rounded-lg border border-status-partial/40 bg-status-partial/8 px-4 py-3 text-sm text-foreground"
                  >
                    Kein aktives Projekt — bitte legen Sie zuerst im Intake ein
                    Projekt an.
                  </p>
                )}
                <SourceTable
                  sources={sourceRows}
                  controlled
                  onUploadFiles={handleUploadSources}
                  onAddTextSource={handleAddTextSource}
                  onAddUrlSource={handleAddUrlSource}
                  onImportSources={handleImportSources}
                  onDeleteSource={handleDeleteSource}
                  acceptExtensions={[".pdf", ".docx", ".txt"]}
                  currentUserName={currentUser.name}
                  openDetailsForId={sourceDetailId}
                  onDetailsOpenChange={(open) => {
                    if (!open) setSourceDetailId(null)
                  }}
                />
                {projectId && capabilities?.features?.web_research && (
                  <PublicResearchPanel
                    projectId={projectId}
                    dataClass={effectiveDataClass ?? "public"}
                    onImported={refreshSources}
                  />
                )}
                {projectId && capabilities?.features?.market_comparison && (
                  <MarketComparisonSection projectId={projectId} />
                )}
              </div>
            ) : (
              <SourceTable
                sources={dummySources}
                currentUserName={currentUser.name}
              />
            )}
          </TabsContent>

          <TabsContent value="evidenz">
            {liveMode ? (
              completedRunId ? (
                <LiveEvidence
                  runId={completedRunId}
                  focusAnchorId={focusAnchorId}
                  onOpenSource={handleOpenSourceFromEvidence}
                />
              ) : (
                <p className="py-10 text-center text-sm text-muted-foreground">
                  Noch keine abgeschlossene Analyse. Starten Sie die Analyse, um
                  Belege zu erzeugen.
                </p>
              )
            ) : (
              <EvidenceTab cards={dummyEvidence} />
            )}
          </TabsContent>
        </Tabs>

        {/* Debug: dialog-variant switcher — hidden from normal user-facing UI */}
        {SHOW_DEBUG_CONTROLS && (
        <div className="mt-10 border-t border-border pt-6">
          <button
            type="button"
            onClick={() => setShowDebugControls((v) => !v)}
            aria-expanded={showDebugControls}
            className={cn(
              "flex items-center gap-1.5 rounded text-xs font-medium text-muted-foreground",
              "outline-none transition-colors hover:text-foreground",
              "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            )}
          >
            {showDebugControls ? (
              <ChevronDown className="size-3.5" />
            ) : (
              <ChevronRight className="size-3.5" />
            )}
            Demo: Dialogvarianten &amp; Seitenzustände testen
          </button>

          {showDebugControls && (
            <div className="mt-4 flex flex-col gap-4">
              {/* Dialog variants */}
              <div>
                <p className="mb-2 text-xs text-muted-foreground">
                  Dialog-Varianten
                </p>
                <div className="flex flex-wrap gap-2">
                  {DIALOG_SCENARIOS.map((scenario) => (
                    <button
                      key={scenario.id}
                      type="button"
                      onClick={() => openDialogWith(scenario)}
                      className={cn(
                        "inline-flex h-8 items-center rounded-full border border-border bg-card px-3 text-xs font-medium text-foreground transition-colors",
                        "hover:bg-accent hover:text-accent-foreground",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      )}
                    >
                      {scenario.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Page analysis states */}
              <div>
                <p className="mb-2 text-xs text-muted-foreground">
                  Seiten-Analysezustand
                </p>
                <div className="flex flex-wrap gap-2">
                  {(
                    [
                      ["idle", "Keine Analyse"],
                      ["running", "Analyse läuft"],
                      ["stopped", "Gestoppt"],
                    ] as const
                  ).map(([state, label]) => (
                    <button
                      key={state}
                      type="button"
                      onClick={() => setAnalysisState(state)}
                      className={cn(
                        "inline-flex h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                        analysisState === state
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-card text-foreground hover:bg-accent hover:text-accent-foreground"
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
        )}
      </div>

      {/* Analyse-Einstellungen dialog */}
      <AnalyseEinstellungenDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        role={activeScenario.role}
        dataClass={dialogDataClass}
        variant={activeScenario.variant}
        serviceAvailability={{
          ki: activeScenario.kiAvailable,
          web: activeScenario.webAvailable,
        }}
        hasActiveRun={activeScenario.hasActiveRun}
        estimateState={activeScenario.estimateState}
        onStart={handleAnalysisStart}
        onCancel={() => setDialogOpen(false)}
      />
    </AppShell>
  )
}
