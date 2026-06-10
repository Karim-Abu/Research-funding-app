"use client"

import * as React from "react"
import { Settings2 } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { AnalyseEinstellungenDialog } from "@/components/run/analyse-einstellungen-dialog"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { AnalyseSettings, DataClass, Role } from "@/lib/types"

// ---------------------------------------------------------------------------
// Scenario definitions — each maps to a distinct dialog state.
// Labels are German (user-visible); ids are English (code-only).
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
    label: "Schätzung n/v",
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
        <div className="mb-6 flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-foreground text-balance">
            Quellen &amp; Evidenz
          </h1>
          <p className="text-sm text-muted-foreground">
            Starten Sie eine Analyse Ihrer hochgeladenen Unterlagen.
          </p>
        </div>

        {/* Primary action */}
        <Button onClick={() => openWith(SCENARIOS[0])}>
          <Settings2 data-icon="inline-start" />
          Analyse-Einstellungen
        </Button>

        {/* Scenario switcher — lets reviewers open each dialog variant */}
        <div className="mt-8 flex flex-col gap-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Weitere Dialogvarianten
          </p>
          <div className="flex flex-wrap gap-2">
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
        </div>

        {lastSettings && (
          <p className="mt-6 text-sm text-muted-foreground">
            Analyse gestartet (Dummy-Bestätigung).
          </p>
        )}
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
