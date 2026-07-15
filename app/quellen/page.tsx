"use client"

import * as React from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Play, ChevronDown, ChevronRight, XCircle } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { AnalyseEinstellungenDialog } from "@/components/run/analyse-einstellungen-dialog"
import { SourceTable } from "@/components/quellen/source-table"
import { PublicResearchPanel } from "@/components/quellen/public-research-panel"
import { MarketComparisonSection } from "@/components/quellen/market-comparison-section"
import {
  AnalysisProgressBanner,
  StoppedAnalysisBanner,
  CompletedAnalysisBanner,
  LocalOnlyBanner,
} from "@/components/quellen/analysis-progress-banner"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import {
  dummySources,
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
import {
  loadIntake,
  setCurrentRunId,
  setSelectedRunId,
  getActiveProjectId,
} from "@/lib/intake-store"
import { useActiveRun } from "@/components/providers/workflow-run-provider"
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
  UPLOAD_HINT_KEY,
  type SourceDocumentDto,
} from "@/lib/sources"
import { getCapabilities, type Capabilities } from "@/lib/capabilities"
import {
  cancelRun,
  createRun,
  getRunPhases,
  liveStatusNotice,
  RunError,
  type RunSettings,
  type RunStatus,
  type RunTechnicalSummaryDto,
} from "@/lib/runs"
import {
  failedPhaseLabel,
  phasesToView,
  type RunPhaseView,
} from "@/lib/run-steps"
import { RunTechnicalDetails } from "@/components/run/run-technical-details"
import { createProcessingConfirmation } from "@/lib/processing-confirmations"
import {
  dataClassificationFromFlat,
  flatFromDataClassification,
  type Origin,
} from "@/lib/data-classification"
import { getProject } from "@/lib/projects"
import {
  computeSourceUsage,
  listEvidence,
  type SourceUsage,
} from "@/lib/evidence"
import { listRequirements } from "@/lib/requirements"

// Map a live contract SourceDocument onto the existing table row shape.
const SOURCE_TYPE_LABEL: Record<string, Source["type"]> = {
  pdf: "PDF",
  docx: "DOCX",
  txt: "Text",
  url: "URL",
}

// Ursachen-spezifische Handlungshinweise (error_code der aktuellen Version).
const NEEDS_INPUT_HINTS: Record<string, string> = {
  SOURCE_PDF_ENCRYPTED:
    "Das PDF ist passwortgeschützt. Bitte entfernen Sie den Passwortschutz oder erfassen Sie den Inhalt als Text.",
  SOURCE_NO_TEXT_LAYER:
    "Kein Textlayer erkannt (vermutlich ein Scan). Bitte verwenden Sie einen digitalen PDF-Export oder erfassen Sie den Inhalt als Text.",
}

function toSourceRow(s: SourceDocumentDto): Source {
  let errorHint: string | undefined
  if (s.status === "failed") {
    errorHint =
      s.error_message ??
      "Die Quelle konnte nicht verarbeitet werden. Bitte Format prüfen, erneut hochladen oder entfernen."
  } else if (s.status === "needs_manual_input") {
    errorHint =
      NEEDS_INPUT_HINTS[s.error_code ?? ""] ??
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
// Page
// ---------------------------------------------------------------------------

// Set to true only during internal prototyping — never in the evaluation view.
const SHOW_DEBUG_CONTROLS = false

export default function QuellenPage() {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
    >
      {/* useSearchParams requires a Suspense boundary in the App Router. */}
      <React.Suspense fallback={null}>
        <QuellenPageContent />
      </React.Suspense>
    </AppShell>
  )
}

function QuellenPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  // Deep link (?source=…): open that source's details directly.
  const sourceFromUrl = searchParams.get("source")

  // Die Evidenz-Ansicht lebt jetzt im Schritt «Analyse & Recherche»
  // (/anforderungen?tab=evidenz) — alte Links/Bookmarks weiterleiten.
  React.useEffect(() => {
    if (searchParams.get("tab") !== "evidenz") return
    const anchor = searchParams.get("anchor")
    router.replace(
      `/anforderungen?tab=evidenz${anchor ? `&anchor=${encodeURIComponent(anchor)}` : ""}`
    )
  }, [searchParams, router])

  // Evidence → source navigation: open that source's details.
  const [sourceDetailId, setSourceDetailId] = React.useState<string | null>(
    sourceFromUrl
  )

  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [activeScenario, setActiveScenario] = React.useState<DialogScenario>(
    DIALOG_SCENARIOS[0]
  )
  const [analysisState, setAnalysisState] =
    React.useState<PageAnalysisState>("idle")
  const [analysisSteps, setAnalysisSteps] =
    React.useState<AnalysisProgressStep[]>(dummyAnalysisSteps)
  // Live-Pfad: echte, persistierte Phasen (kein erfundener Prozentwert).
  const [runPhases, setRunPhases] = React.useState<RunPhaseView[] | null>(null)
  const [runTechnical, setRunTechnical] =
    React.useState<RunTechnicalSummaryDto | null>(null)
  const [partialLabel, setPartialLabel] = React.useState<string | null>(null)
  // Ehrlicher Live-Status (partial_live etc.) — nie ein stiller Fallback.
  const [liveNotice, setLiveNotice] = React.useState<string | null>(null)
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
  // Im Projekt gespeicherte Klassifizierung (Backend ist die Wahrheit) — deckt
  // Projekte ohne Intake-Session ab (z. B. API-erstellt oder frischer Browser).
  const [projectDataClass, setProjectDataClass] =
    React.useState<DataClass | null>(null)
  const [projectOrigin, setProjectOrigin] =
    React.useState<Origin>("real_project")

  // Restriktivste bekannte Einstufung gewinnt (nie Downgrade); ohne jedes
  // Signal bleibt null und die Konsumenten fallen fail-closed auf
  // "confidential" zurück.
  const knownDataClasses: DataClass[] = [
    ...(backendDataClass ? [backendDataClass] : []),
    ...(projectDataClass ? [projectDataClass] : []),
    ...(intake ? [intake.vertraulichkeit || ("confidential" as DataClass)] : []),
  ]
  const effectiveDataClass: DataClass | null = knownDataClasses.length
    ? mostRestrictiveDataClass(knownDataClasses)
    : null

  // Run lifecycle: the page only starts a run and polls its status via the
  // API layer; the progression itself lives behind lib/api.ts (mock or bridge).
  const runIdRef = React.useRef<string | null>(null)
  const pollTimer = React.useRef<ReturnType<typeof setInterval> | undefined>(
    undefined
  )
  React.useEffect(
    () => () => {
      clearInterval(pollTimer.current)
    },
    []
  )

  const stopPolling = React.useCallback(() => {
    clearInterval(pollTimer.current)
    pollTimer.current = undefined
  }, [])

  // Persistierten Phasenstand des Laufs nachladen (Live-Pfad). Transiente
  // Fehler behalten den letzten bekannten Stand — kein Flackern, kein Raten.
  const refreshRunPhases = React.useCallback(
    async (runId: string): Promise<RunStatus | null> => {
      try {
        const data = await getRunPhases(runId)
        setRunPhases(phasesToView(data.phases))
        setRunTechnical(data.technical)
        setPartialLabel(failedPhaseLabel(data.phases))
        setLiveNotice(liveStatusNotice(data.live_execution_status))
        return data.run_status
      } catch {
        // letzte bekannte Phasen behalten; der Watcher versucht es erneut.
        return null
      }
    },
    []
  )

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
    // Live: die echten Phasen kommen aus GET /runs/{id}/phases; bis zum
    // ersten Poll zeigt das Banner nur «Analyse läuft».
    setRunPhases(liveMode ? [] : null)
    setRunTechnical(null)
    setPartialLabel(null)
    if (!liveMode) {
      setAnalysisSteps(
        dummyAnalysisSteps.map((s, i) => ({
          ...s,
          state: i === 0 ? ("running" as const) : ("pending" as const),
        }))
      )
    }
    setAnalysisState("running")
    setCanResume(false)
    setRunCost(undefined)
    try {
      if (liveMode && projectId) {
        // Modell- oder Demo-Läufe verwenden den kontrollierten cloud_assisted-
        // Runmodus. Herkunft, Quellen, Bestätigung und ProviderPolicy werden im
        // Backend erneut fail-closed geprüft. Ein lokaler Adapter existiert nicht.
        const processedVersionIds = liveSources
          .filter((s) => s.status === "processed" && s.current_source_version_id)
          .map((s) => s.current_source_version_id as string)
        const useCloud =
          settings.ki &&
          settings.cloudConfirmed === true &&
          processedVersionIds.length > 0

        // Run-Budgets aus dem Dialog: KI-Aufrufe (Default 25) und — nur für
        // öffentliche Cloud-Läufe mit aktivierter Webrecherche — die Zahl der
        // Suchanfragen. Beide Limits werden im Backend durchgesetzt.
        const maxLlmCalls = settings.maxLlmCalls ?? 25
        const maxWebCalls = settings.web ? (settings.maxWebCalls ?? 5) : 0
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
            max_llm_calls: maxLlmCalls,
            max_web_calls: maxWebCalls,
            source_version_ids: processedVersionIds,
            internal_cloud_confirmation_id: confirmation.confirmation_id,
          }
        }
        const accepted = await createRun(projectId, runSettings)
        runIdRef.current = accepted.resource_id
        setCurrentRunId(accepted.resource_id)
        // Echter, persistierter Phasen-/Run-Status statt Prozent-Heuristik.
        watchRun(accepted.resource_id)
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
  // Zentrale Run-Auswahl (Ladder): dieselbe Run-ID wie auf allen anderen
  // Screens; reload() nach einem abgeschlossenen Lauf auf dieser Seite.
  const {
    runId: completedRunId,
    runs: workflowRuns,
    reload: reloadWorkflow,
  } = useActiveRun()
  const [projectId, setProjectId] = React.useState<string | null>(null)
  const [liveSources, setLiveSources] = React.useState<SourceDocumentDto[]>([])
  const [localSourceRows, setLocalSourceRows] = React.useState<Source[]>([])
  const [capabilities, setCapabilities] = React.useState<Capabilities | null>(
    null
  )
  // Einmaliger Hinweis aus dem Intake: Projekt gespeichert, Upload offen.
  const [uploadHint, setUploadHint] = React.useState(false)

  React.useEffect(() => {
    if (!liveMode) return
    setProjectId(getActiveProjectId())
    void getCapabilities().then(setCapabilities)
    try {
      if (window.sessionStorage.getItem(UPLOAD_HINT_KEY) === "1") {
        window.sessionStorage.removeItem(UPLOAD_HINT_KEY)
        setUploadHint(true)
      }
    } catch {
      // Storage blockiert — kein Hinweis.
    }
  }, [liveMode])

  // Gespeicherte Projektklasse nachladen; bei Fehler bleibt der
  // fail-closed-Fallback ("confidential") bestehen.
  React.useEffect(() => {
    if (!liveMode || !projectId) return
    let active = true
    getProject(projectId)
      .then((p) => {
        if (active)
          setProjectDataClass(flatFromDataClassification(p.data_classification))
        if (active) setProjectOrigin(p.data_classification.origin)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [liveMode, projectId])

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

  // EIN Watcher für Start UND Reload-Resume: verfolgt den persistierten
  // Phasen-/Run-Status bis zum terminalen Zustand. Einzelne fehlgeschlagene
  // Polls werden übersprungen — die Anzeige verliert den Lauf nie.
  const watchRun = React.useCallback(
    (runId: string) => {
      stopPolling()
      const tick = async () => {
        const status = await refreshRunPhases(runId)
        if (status === "completed") {
          stopPolling()
          // Der eben abgeschlossene Lauf wird zur expliziten Auswahl
          // (Ladder-Stufe 2), bis der Projekt-Refetch die vom Backend
          // gesetzte active_run_id liefert.
          setSelectedRunId(runId)
          reloadWorkflow()
          setAnalysisState("completed")
          void refreshSources()
        } else if (
          status === "failed" ||
          status === "stopped" ||
          status === "cancelled"
        ) {
          stopPolling()
          setCanResume(false)
          setAnalysisState("stopped")
          if (status === "failed") {
            setApiError("Die Analyse konnte nicht abgeschlossen werden.")
          }
        }
      }
      void tick()
      pollTimer.current = setInterval(
        () => void tick(),
        (capabilities?.polling_interval_seconds ?? 1) * 1000
      )
    },
    [capabilities, refreshRunPhases, stopPolling, reloadWorkflow, refreshSources]
  )

  // Reload-Fähigkeit: läuft für dieses Projekt bereits eine Analyse, wird die
  // Fortschrittsansicht nach einem Seiten-Reload wieder aufgenommen — die
  // Phasen sind im Backend persistiert, nichts geht verloren. Die Run-Liste
  // kommt aus der zentralen Workflow-Wahrheit (useActiveRun), nie aus einer
  // eigenen Abfrage der Seite.
  React.useEffect(() => {
    if (!liveMode) return
    const active = workflowRuns.find(
      (r) => r.status === "running" || r.status === "created"
    )
    if (!active || runIdRef.current === active.run_id) return
    runIdRef.current = active.run_id
    setCurrentRunId(active.run_id)
    setRunPhases([])
    setAnalysisState("running")
    watchRun(active.run_id)
  }, [liveMode, workflowRuns, watchRun])

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

  const handleUploadSources = React.useCallback(
    async (
      files: File[],
      dataClass: DataClass,
      onProgress?: (percent: number) => void
    ) => {
      if (!projectId) throw new Error("Kein aktives Projekt ausgewählt.")
      await uploadFiles(
        projectId,
        files,
        dataClassificationFromFlat(dataClass),
        { onProgress }
      )
      await refreshSources()
    },
    [projectId, refreshSources]
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
    async ({ title, text, dataClass }: { title: string; text: string; dataClass: DataClass }) => {
      if (!projectId) throw new Error("Kein aktives Projekt ausgewählt.")
      await createTextSource(
        projectId,
        title,
        text,
        dataClassificationFromFlat(dataClass)
      )
      await refreshSources()
    },
    [projectId, refreshSources]
  )

  const handleAddUrlSource = React.useCallback(
    async ({ url, kind, dataClass }: { url: string; kind: UrlSourceKind; dataClass: DataClass }) => {
      if (!projectId) throw new Error("Kein aktives Projekt ausgewählt.")
      const canUseBackendUrlImport = Boolean(
        capabilities?.features?.url_import ||
          capabilities?.supported_source_types.includes("url")
      )
      const classification = dataClassificationFromFlat(dataClass)

      if (canUseBackendUrlImport) {
        try {
          await createUrlSource(
            projectId,
            url,
            `${URL_SOURCE_KIND_LABELS[kind]}: ${url}`,
            classification
          )
          await refreshSources()
          return
        } catch {
          // URL import unavailable in this deployment — fall through to the
          // page-level hint instead of fabricating a source row.
        }
      }

      setApiError(
        "URL-Import ist in dieser Umgebung nicht verfügbar. Kopieren Sie den Webseiteninhalt und fügen Sie ihn als Textquelle ein."
      )
    },
    [capabilities, projectId, refreshSources]
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

  // View-scoped source usage (Fundstellen + Anforderungen of the completed
  // run) for the source-details dialog. undefined = not available.
  const [sourceUsage, setSourceUsage] = React.useState<
    Map<string, SourceUsage> | undefined
  >(undefined)
  React.useEffect(() => {
    if (!liveMode || !completedRunId) {
      setSourceUsage(undefined)
      return
    }
    let cancelled = false
    Promise.all([
      listEvidence(completedRunId),
      listRequirements(completedRunId),
    ])
      .then(([anchors, requirements]) => {
        if (!cancelled) setSourceUsage(computeSourceUsage(anchors, requirements))
      })
      .catch(() => {
        if (!cancelled) setSourceUsage(undefined)
      })
    return () => {
      cancelled = true
    }
  }, [liveMode, completedRunId])

  const sourceRows: Source[] = liveMode
    ? [...localSourceRows, ...liveSources.map(toSourceRow)]
    : dummySources

  // STEP 12: the live "Analyse starten" action stays disabled until the server
  // capability (features.runs) enables it (Milestone 4). Mock mode is unaffected.
  const runsEnabled = !liveMode || Boolean(capabilities?.features?.runs)

  return (
    <>
      <div className="mx-auto max-w-5xl px-6 py-8">

        {/* Page header */}
        <div className="mb-6 flex items-start justify-between gap-4">
          <div className="flex flex-col gap-2">
            <h1 className="text-balance text-2xl font-semibold text-foreground">
              Quellen
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

        {/* Intake-Hinweis: Projekt gespeichert, Unterlagen-Upload offen */}
        {uploadHint && (
          <div
            role="alert"
            className="mb-4 rounded-lg border border-status-partial/40 bg-status-partial/8 px-4 py-3 text-sm text-foreground"
          >
            Das Projekt wurde gespeichert, aber die Unterlagen konnten nicht
            hochgeladen werden. Bitte laden Sie sie hier erneut hoch.
          </div>
        )}

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
              phases={runPhases ?? undefined}
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
          <div className="mb-4 flex flex-col gap-3">
            <CompletedAnalysisBanner
              partialPhaseLabel={partialLabel}
              liveNotice={liveNotice}
              onGoToRequirements={() => router.push("/anforderungen")}
              onShowEvidence={() => router.push("/anforderungen?tab=evidenz")}
            />
            {liveMode && runTechnical && (
              <RunTechnicalDetails technical={runTechnical} />
            )}
          </div>
        )}

        {/* Quellen — die Evidenz-Ansicht lebt unter «Analyse & Recherche» */}
        {liveMode ? (
          <div className="flex flex-col gap-6">
            {!projectId && (
              <p
                role="alert"
                className="rounded-lg border border-status-partial/40 bg-status-partial/8 px-4 py-3 text-sm text-foreground"
              >
                Kein aktives Projekt — bitte legen Sie zuerst unter «Projekt
                anlegen» ein Projekt an.
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
              defaultDataClass={effectiveDataClass ?? "confidential"}
              currentUserName={currentUser.name}
              openDetailsForId={sourceDetailId}
              onDetailsOpenChange={(open) => {
                if (!open) setSourceDetailId(null)
              }}
              sourceUsage={sourceUsage}
              onShowEvidence={() => router.push("/anforderungen?tab=evidenz")}
            />
            {projectId && capabilities?.features?.web_research && (
              <PublicResearchPanel
                projectId={projectId}
                dataClass={effectiveDataClass ?? "confidential"}
                onImported={refreshSources}
              />
            )}
            {projectId && capabilities?.features?.market_comparison && (
              <MarketComparisonSection
                projectId={projectId}
                sourceNames={Object.fromEntries(
                  liveSources.map((s) => [s.source_id, s.name])
                )}
              />
            )}
          </div>
        ) : (
          <SourceTable
            sources={dummySources}
            currentUserName={currentUser.name}
            onShowEvidence={() => router.push("/anforderungen?tab=evidenz")}
          />
        )}

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
          ki: liveMode
            ? Boolean(
                capabilities?.generation_mode &&
                  capabilities.generation_mode !== "unavailable" &&
                  // Live konfiguriert, aber Provider fehlt ⇒ KI ist NICHT
                  // verfügbar — es erscheint kein Demo-Ergebnis als Ersatz.
                  capabilities.generation_mode !== "live_unavailable"
              )
            : activeScenario.kiAvailable,
          web: activeScenario.webAvailable,
          generationMode: liveMode
            ? (capabilities?.generation_mode ?? "unavailable")
            : activeScenario.kiAvailable
              ? "fake_demo"
              : "unavailable",
          unavailableReason: capabilities?.generation_unavailable_reason ?? undefined,
        }}
        hasActiveRun={activeScenario.hasActiveRun}
        projectId={liveMode ? (projectId ?? undefined) : undefined}
        projectOrigin={liveMode ? projectOrigin : "synthetic"}
        onStart={handleAnalysisStart}
        onCancel={() => setDialogOpen(false)}
      />
    </>
  )
}
