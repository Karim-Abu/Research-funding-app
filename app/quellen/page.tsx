"use client"

import * as React from "react"
import { Settings2 } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { AnalyseEinstellungenDialog } from "@/components/run/analyse-einstellungen-dialog"
import { currentUser, memberUser, projects, activeProjectId } from "@/lib/mock-data"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type {
  AnalyseSettings,
  DataClass,
  Role,
  ServiceAvailability,
} from "@/lib/types"

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
  const [role, setRole] = React.useState<Role>("lead_admin")
  const [dataClass, setDataClass] = React.useState<DataClass>("public_synthetic")
  const [kiAvailable, setKiAvailable] = React.useState(true)
  const [hasActiveRun, setHasActiveRun] = React.useState(false)
  const [estimate, setEstimate] = React.useState<
    "ready" | "loading" | "unavailable"
  >("ready")
  const [lastSettings, setLastSettings] = React.useState<AnalyseSettings | null>(
    null
  )

  const serviceAvailability: ServiceAvailability = {
    ki: kiAvailable,
    web: true,
  }

  return (
    <AppShell
      user={role === "lead_admin" ? currentUser : memberUser}
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
            „Analyse-Einstellungen“ konfigurieren Sie KI- und Webdienste.
          </p>
        </div>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">Demo-Steuerung</CardTitle>
            <CardDescription>
              Wählen Sie Rolle, Datenklasse und Dienstverfügbarkeit, um die
              verschiedenen Zustände des Dialogs zu sehen.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
              <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
                Rolle
                <Select value={role} onValueChange={(v) => setRole(v as Role)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="lead_admin">
                        Projektleitung / Admin
                      </SelectItem>
                      <SelectItem value="member">Projektmitglied</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </label>
              <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
                Datenklasse
                <Select
                  value={dataClass}
                  onValueChange={(v) => setDataClass(v as DataClass)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="public_synthetic">
                        Öffentlich (synthetisch)
                      </SelectItem>
                      <SelectItem value="public_external">
                        Öffentlich (extern)
                      </SelectItem>
                      <SelectItem value="internal">Intern</SelectItem>
                      <SelectItem value="confidential">Vertraulich</SelectItem>
                      <SelectItem value="nda">NDA</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </label>
              <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
                KI-Dienst
                <Select
                  value={kiAvailable ? "on" : "off"}
                  onValueChange={(v) => setKiAvailable(v === "on")}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="on">Verfügbar</SelectItem>
                      <SelectItem value="off">Nicht verfügbar</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </label>
              <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
                Aktiver Lauf
                <Select
                  value={hasActiveRun ? "yes" : "no"}
                  onValueChange={(v) => setHasActiveRun(v === "yes")}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="no">Kein Lauf aktiv</SelectItem>
                      <SelectItem value="yes">Lauf läuft bereits</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </label>
              <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
                Schätzung
                <Select
                  value={estimate}
                  onValueChange={(v) =>
                    setEstimate(v as "ready" | "loading" | "unavailable")
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="ready">Verfügbar</SelectItem>
                      <SelectItem value="loading">Wird berechnet</SelectItem>
                      <SelectItem value="unavailable">
                        Nicht verfügbar
                      </SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </label>
            </div>
          </CardContent>
        </Card>

        <Button onClick={() => setOpen(true)}>
          <Settings2 data-icon="inline-start" />
          Analyse-Einstellungen
        </Button>

        {lastSettings && (
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="text-base">
                Zuletzt gestartete Analyse (Dummy)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="overflow-x-auto rounded-md bg-muted p-4 text-xs text-muted-foreground">
                {JSON.stringify(lastSettings, null, 2)}
              </pre>
            </CardContent>
          </Card>
        )}
      </div>

      <AnalyseEinstellungenDialog
        open={open}
        onOpenChange={setOpen}
        role={role}
        dataClass={dataClass}
        serviceAvailability={serviceAvailability}
        hasActiveRun={hasActiveRun}
        estimateState={estimate}
        onStart={(settings) => {
          setLastSettings(settings)
          setOpen(false)
        }}
        onCancel={() => setOpen(false)}
      />
    </AppShell>
  )
}
