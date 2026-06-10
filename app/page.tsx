"use client"

import { AppShell } from "@/components/shell/app-shell"
import { WorkflowStepper } from "@/components/shell/workflow-stepper"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

const stepStatus = [
  "done",
  "done",
  "done",
  "current",
  "todo",
  "todo",
  "todo",
  "todo",
] as const

export default function DashboardPage() {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
    >
      <div className="mx-auto max-w-5xl px-6 py-8">
        <div className="mb-6 flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-foreground text-balance">
            Dashboard
          </h1>
          <p className="text-sm text-muted-foreground">
            Überblick über den aktuellen Stand Ihres Innovationsprojekts
            (Dummy-Daten).
          </p>
        </div>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">Arbeitsablauf</CardTitle>
            <CardDescription>
              Acht Schritte von der Aufnahme bis zur Abgabe.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <WorkflowStepper
              currentStep={4}
              stepStatus={[...stepStatus]}
              variant="full"
            />
          </CardContent>
        </Card>

        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Antragsfortschritt
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold text-foreground">48%</p>
              <p className="mt-1 text-xs text-muted-foreground">
                5 von 12 Abschnitten
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Offene Anforderungen
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold text-foreground">3</p>
              <div className="mt-2 flex flex-wrap gap-1">
                <Badge
                  variant="secondary"
                  className="bg-status-partial/15 text-status-partial"
                >
                  2 teilweise
                </Badge>
                <Badge
                  variant="secondary"
                  className="bg-status-open/15 text-status-open"
                >
                  1 offen
                </Badge>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Verbrauch (Dummy)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold text-foreground">CHF 12.40</p>
              <p className="mt-1 text-xs text-muted-foreground">
                von CHF 50.00 Budget
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  )
}
