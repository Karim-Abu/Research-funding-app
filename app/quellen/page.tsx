"use client"

import * as React from "react"
import { Play, ChevronDown, ChevronRight } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { AnalyseEinstellungenDialog } from "@/components/run/analyse-einstellungen-dialog"
import { SourceTable } from "@/components/quellen/source-table"
import { EvidenceTab } from "@/components/quellen/evidence-tab"
import {
  AnalysisProgressBanner,
  StoppedAnalysisBanner,
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
  type PageAnalysisState,
} from "@/lib/quellen-mock-data"
import type { AnalyseSettings, DataClass, Role } from "@/lib/types"

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
    label: "Intern (Bestätigung)",
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
  "todo",
  "todo",
  "todo",
  "todo",
  "todo",
  "todo",
] as const

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

// Set to true only during internal prototyping — never in the evaluation view.
const SHOW_DEBUG_CONTROLS = false

export default function QuellenPage() {
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [activeScenario, setActiveScenario] = React.useState<DialogScenario>(
    DIALOG_SCENARIOS[0]
  )
  const [analysisState, setAnalysisState] =
    React.useState<PageAnalysisState>("idle")
  const [showDebugControls, setShowDebugControls] = React.useState(false)

  // The active scenario's dataClass drives the local-only banner.
  const dataClass = activeScenario.dataClass
  const isLocalOnly = dataClass === "confidential" || dataClass === "nda"

  function openDialogWith(scenario: DialogScenario) {
    setActiveScenario(scenario)
    setDialogOpen(true)
  }

  function handleAnalysisStart(_settings: AnalyseSettings) {
    setDialogOpen(false)
    setAnalysisState("running")
  }

  function handleAnalysisStop() {
    setAnalysisState("stopped")
  }

  function handleAnalysisResume() {
    setAnalysisState("running")
  }

  const sourceCount = dummySources.length
  const evidenceCount = dummyEvidence.length

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
          <div className="flex flex-col gap-1">
            <h1 className="text-balance text-2xl font-semibold text-foreground">
              Quellen &amp; Evidenz
            </h1>
            <p className="text-sm text-muted-foreground">
              Laden Sie Unterlagen hoch. Die Plattform erkennt daraus Anforderungen und passende Belege.
            </p>
          </div>

          {/* Primary action — only shown when no analysis is running */}
          {analysisState !== "running" && (
            <Button
              onClick={() => openDialogWith(DIALOG_SCENARIOS[0])}
              className="shrink-0"
            >
              <Play className="mr-1.5 size-4" />
              Analyse starten
            </Button>
          )}
        </div>

        {/* Confidentiality banner */}
        {isLocalOnly && <div className="mb-4"><LocalOnlyBanner /></div>}

        {/* Analysis state banners */}
        {analysisState === "running" && (
          <div className="mb-4">
            <AnalysisProgressBanner
              steps={dummyAnalysisSteps}
              onStop={handleAnalysisStop}
            />
          </div>
        )}
        {analysisState === "stopped" && (
          <div className="mb-4">
            <StoppedAnalysisBanner onResume={handleAnalysisResume} />
          </div>
        )}

        {/* Tabs */}
        <Tabs defaultValue="quellen">
          <TabsList className="mb-6">
            <TabsTrigger value="quellen">
              Quellen ({sourceCount})
            </TabsTrigger>
            <TabsTrigger value="evidenz">
              Evidenz ({evidenceCount})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="quellen">
            <SourceTable sources={dummySources} />
          </TabsContent>

          <TabsContent value="evidenz">
            <EvidenceTab cards={dummyEvidence} />
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
        dataClass={activeScenario.dataClass}
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
