"use client"

import * as React from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Play, ChevronDown, ChevronRight, XCircle } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { AnalyseEinstellungenDialog } from "@/components/run/analyse-einstellungen-dialog"
import { SourceTable } from "@/components/quellen/source-table"
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
  type AnalysisProgressStep,
  type PageAnalysisState,
  type Source,
} from "@/lib/quellen-mock-data"
import {
  startRun,
  getRun,
  stopRun,
  resumeRun,
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
  deleteSource,
  type SourceDocumentDto,
} from "@/lib/sources"
import { getCapabilities, type Capabilities } from "@/lib/capabilities"
import { listProjectRuns } from "@/lib/runs"
import { LiveEvidence } from "@/components/quellen/live-evidence"
import { dataClassificationFromFlat } from "@/lib/data-classification"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"

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
    errorHint = s.error_message ?? "Die Datei konnte nicht verarbeitet werden."
  } else if (s.status === "needs_manual_input") {
    errorHint =
      "Kein durchsuchbarer Text gefunden — bitte Datei prüfen oder Inhalt als Text erfassen."
  }
  return {
    id: s.source_id,
    name: s.name,
    type: SOURCE_TYPE_LABEL[s.type] ?? "Text",
    status: s.status,
    addedBy: "—",
    addedAt: s.created_at
      ? new Date(s.created_at).toLocaleString("de-CH")
      : "—",
    errorHint,
  }
}

// Minimal text-source form (live mode) — contract createTextSource.
function TextSourceForm({
  onAdd,
  disabled,
}: {
  onAdd: (name: string, text: string) => Promise<void>
  disabled?: boolean
}) {
  const [open, setOpen] = React.useState(false)
  const [name, setName] = React.useState("")
  const [text, setText] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  async function submit() {
    if (!name.trim() || !text.trim()) return
    setBusy(true)
    setError(null)
    try {
      await onAdd(name.trim(), text)
      setName("")
      setText("")
      setOpen(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hinzufügen fehlgeschlagen.")
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="self-start"
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        Text als Quelle hinzufügen
      </Button>
    )
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border p-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="text-source-name">Name</Label>
        <Input
          id="text-source-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="z. B. Gesprächsnotiz"
          disabled={busy}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="text-source-text">Text</Label>
        <Textarea
          id="text-source-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          placeholder="Inhalt der Textquelle…"
          disabled={busy}
        />
      </div>
      {error && (
        <p role="alert" className="text-xs text-status-blocker">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          type="button"
          size="sm"
          onClick={submit}
          disabled={busy || !name.trim() || !text.trim()}
        >
          Hinzufügen
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setOpen(false)}
          disabled={busy}
        >
          Abbrechen
        </Button>
      </div>
    </div>
  )
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
    dataClass: "public_synthetic",
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
    dataClass: "public_synthetic",
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
    id: "nda",
    label: "NDA",
    role: "lead_admin",
    dataClass: "nda",
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
    dataClass: "public_synthetic",
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
    dataClass: "public_synthetic",
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
    dataClass: "public_synthetic",
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
    dataClass: "public_synthetic",
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
  "upcoming",
] as const

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

// Set to true only during internal prototyping — never in the evaluation view.
const SHOW_DEBUG_CONTROLS = false

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

  const [activeTab, setActiveTab] = React.useState<QuellenTab>(tabFromUrl)
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
      ? mostRestrictiveDataClass([intake.vertraulichkeit || "public_synthetic"])
      : null)

  // Run lifecycle: the page only starts a run and polls its status via the
  // API layer; the progression itself lives behind lib/api.ts (mock or bridge).
  const runIdRef = React.useRef<string | null>(null)
  const pollTimer = React.useRef<ReturnType<typeof setInterval> | undefined>(
    undefined
  )
  React.useEffect(() => () => clearInterval(pollTimer.current), [])

  const stopPolling = React.useCallback(() => {
    clearInterval(pollTimer.current)
    pollTimer.current = undefined
  }, [])

  const startPolling = React.useCallback(() => {
    stopPolling()
    pollTimer.current = setInterval(async () => {
      const runId = runIdRef.current
      if (!runId) return
      try {
        const dto = await getRun(runId)
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
    setDialogOpen(false)
    setApiError(null)
    setAnalysisSteps(
      dummyAnalysisSteps.map((s, i) => ({
        ...s,
        state: i === 0 ? ("running" as const) : ("pending" as const),
      }))
    )
    setAnalysisState("running")
    try {
      const startRequest: RunStartRequestDto = {
        intake,
        settings,
        effectiveDataClass,
      }
      const { runId } = await startRun(startRequest)
      runIdRef.current = runId
      setCurrentRunId(runId)
      startPolling()
    } catch (e) {
      setAnalysisState("idle")
      setApiError(
        e instanceof ApiError ? e.message : BRIDGE_UNREACHABLE_MESSAGE
      )
    }
  }

  function handleAnalysisStop() {
    stopPolling()
    setAnalysisState("stopped")
    const runId = runIdRef.current
    if (!runId) return
    // Refresh canResume/cost once from the stopped run.
    void stopRun(runId)
      .then(() => getRun(runId))
      .then((dto) => {
        setCanResume(dto.canResume ?? false)
        setRunCost(dto.cost)
      })
      .catch(() => setCanResume(false))
  }

  function handleAnalysisResume() {
    const runId = runIdRef.current
    if (!runId) return
    setAnalysisState("running")
    resumeRun(runId)
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
  const [completedRunId, setCompletedRunId] = React.useState<string | null>(null)
  const [capabilities, setCapabilities] = React.useState<Capabilities | null>(
    null
  )

  React.useEffect(() => {
    if (!liveMode) return
    setProjectId(getActiveProjectId())
    void getCapabilities().then(setCapabilities)
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
    () => dataClassificationFromFlat(effectiveDataClass ?? "public_synthetic"),
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
      void deleteSource(id).then(refreshSources).catch(() => undefined)
    },
    [refreshSources]
  )

  const handleAddTextSource = React.useCallback(
    async (name: string, text: string) => {
      if (!projectId) throw new Error("Kein aktives Projekt ausgewählt.")
      await createTextSource(projectId, name, text, sourceClassification)
      await refreshSources()
    },
    [projectId, sourceClassification, refreshSources]
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
    ? liveSources.map(toSourceRow)
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
                  onDeleteSource={handleDeleteSource}
                  acceptExtensions={[".pdf", ".docx", ".txt"]}
                />
                <TextSourceForm
                  onAdd={handleAddTextSource}
                  disabled={!projectId}
                />
              </div>
            ) : (
              <SourceTable sources={dummySources} />
            )}
          </TabsContent>

          <TabsContent value="evidenz">
            {liveMode ? (
              completedRunId ? (
                <LiveEvidence runId={completedRunId} />
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
