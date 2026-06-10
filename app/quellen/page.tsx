"use client"

import * as React from "react"
import { Settings2, ChevronDown, ChevronRight, FileText, Link2 } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { AnalyseEinstellungenDialog } from "@/components/run/analyse-einstellungen-dialog"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { AnalyseSettings, DataClass, Role } from "@/lib/types"

// ---------------------------------------------------------------------------
// Scenario definitions — code-only identifiers; labels are German.
// ---------------------------------------------------------------------------
type EstimateState = "ready" | "loading" | "unavailable"

interface Scenario {
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

const SCENARIOS: Scenario[] = [
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
    id: "ki-offline",
    label: "KI nicht verfügbar",
    role: "lead_admin",
    dataClass: "public_synthetic",
    kiAvailable: false,
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

export default function QuellenPage() {
  const [open, setOpen] = React.useState(false)
  const [activeScenario, setActiveScenario] = React.useState<Scenario>(
    SCENARIOS[0]
  )
  const [lastSettings, setLastSettings] = React.useState<AnalyseSettings | null>(
    null
  )
  // Debug controls are hidden by default.
  const [showDebugControls, setShowDebugControls] = React.useState(false)

  function openWith(scenario: Scenario) {
    setActiveScenario(scenario)
    setOpen(true)
  }

  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={2}
      stepStatus={[...quellenStepStatus]}
    >
      <div className="mx-auto max-w-4xl px-6 py-8">

        {/* Page header */}
        <div className="mb-6 flex flex-col gap-1">
          <h1 className="text-balance text-2xl font-semibold text-foreground">
            Quellen &amp; Evidenz
          </h1>
          <p className="text-sm text-muted-foreground">
            Laden Sie Unterlagen hoch und starten Sie eine Analyse, um
            Evidenz für Ihren Antrag zu gewinnen.
          </p>
        </div>

        {/* Primary action */}
        <Button onClick={() => openWith(SCENARIOS[0])}>
          <Settings2 data-icon="inline-start" />
          Analyse-Einstellungen
        </Button>

        {lastSettings && (
          <p className="mt-4 text-sm text-muted-foreground">
            Analyse gestartet (Dummy-Bestätigung).
          </p>
        )}

        {/* Content placeholders */}
        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-3 rounded-lg border border-dashed border-border bg-muted/30 p-5">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <FileText className="size-4 shrink-0 text-muted-foreground" />
              Hochgeladene Unterlagen
            </div>
            <p className="text-xs text-muted-foreground">
              Dieser Bereich zeigt die hochgeladenen Quelldokumente des
              Projekts. Noch nicht implementiert.
            </p>
          </div>
          <div className="flex flex-col gap-3 rounded-lg border border-dashed border-border bg-muted/30 p-5">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Link2 className="size-4 shrink-0 text-muted-foreground" />
              Evidenz-Übersicht
            </div>
            <p className="text-xs text-muted-foreground">
              Hier erscheinen die aus der Analyse gewonnenen Belege,
              geordnet nach Abschnitt. Noch nicht implementiert.
            </p>
          </div>
        </div>

        {/* Debug: collapsible dialog-variant switcher — hidden by default */}
        <div className="mt-10 border-t border-border pt-6">
          <button
            type="button"
            onClick={() => setShowDebugControls((v) => !v)}
            className={cn(
              "flex items-center gap-1.5 rounded text-xs font-medium text-muted-foreground",
              "outline-none transition-colors hover:text-foreground",
              "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            )}
            aria-expanded={showDebugControls}
          >
            {showDebugControls ? (
              <ChevronDown className="size-3.5" />
            ) : (
              <ChevronRight className="size-3.5" />
            )}
            Demo: Dialogvarianten testen
          </button>

          {showDebugControls && (
            <div className="mt-3 flex flex-wrap gap-2">
              {SCENARIOS.slice(1).map((scenario) => (
                <button
                  key={scenario.id}
                  type="button"
                  onClick={() => openWith(scenario)}
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
          )}
        </div>
      </div>

      <AnalyseEinstellungenDialog
        open={open}
        onOpenChange={setOpen}
        role={activeScenario.role}
        dataClass={activeScenario.dataClass}
        variant={activeScenario.variant}
        serviceAvailability={{
          ki: activeScenario.kiAvailable,
          web: activeScenario.webAvailable,
        }}
        hasActiveRun={activeScenario.hasActiveRun}
        estimateState={activeScenario.estimateState}
        onStart={(settings) => {
          setLastSettings(settings)
          setOpen(false)
        }}
        onCancel={() => setOpen(false)}
      />
    </AppShell>
  )
}
