"use client"

import * as React from "react"
import { Settings2 } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { AnalyseEinstellungenDialog } from "@/components/run/analyse-einstellungen-dialog"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { Button } from "@/components/ui/button"
import type { AnalyseSettings } from "@/lib/types"

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
  const [lastSettings, setLastSettings] = React.useState<AnalyseSettings | null>(
    null
  )

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
            Starten Sie eine Analyse Ihrer hochgeladenen Unterlagen. Über
            „Analyse-Einstellungen" konfigurieren Sie KI- und Webdienste.
          </p>
        </div>

        <Button onClick={() => setOpen(true)}>
          <Settings2 data-icon="inline-start" />
          Analyse-Einstellungen
        </Button>

        {lastSettings && (
          <p className="mt-4 text-sm text-muted-foreground">
            Analyse gestartet (Dummy-Bestätigung).
          </p>
        )}
      </div>

      <AnalyseEinstellungenDialog
        open={open}
        onOpenChange={setOpen}
        role={currentUser.role}
        dataClass="public_synthetic"
        serviceAvailability={{ ki: true, web: true }}
        hasActiveRun={false}
        estimateState="ready"
        onStart={(settings) => {
          setLastSettings(settings)
          setOpen(false)
        }}
        onCancel={() => setOpen(false)}
      />
    </AppShell>
  )
}
