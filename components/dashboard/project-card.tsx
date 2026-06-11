"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import type { DashboardProject, NextAction, WarningBadge } from "@/lib/types"

// ---------------------------------------------------------------------------
// Label maps — all German, no forbidden terms.
// ---------------------------------------------------------------------------
const NEXT_ACTION_LABELS: Record<NextAction, string> = {
  upload_sources: "Quellen hochladen",
  start_analysis: "Analyse starten",
  review_analysis: "Analyse prüfen",
  continue_draft: "Entwurf weiterbearbeiten",
  approve_review: "Review freigeben",
  create_export: "Export erstellen",
  resume_analysis: "Analyse fortsetzen",
}

const WARNING_BADGE_CONFIG: Record<
  WarningBadge,
  { label: string; className: string }
> = {
  durchlauf_gestoppt: {
    label: "Durchlauf gestoppt",
    className: "bg-destructive/10 text-destructive border-destructive/20",
  },
  freigabe_offen: {
    label: "Freigabe offen",
    className: "bg-status-partial/10 text-status-partial border-status-partial/20",
  },
}

// ---------------------------------------------------------------------------
// ProjectCard
// ---------------------------------------------------------------------------
interface ProjectCardProps {
  project: DashboardProject
  onAction: (projectId: string, action: NextAction | "view_progress") => void
}

export function ProjectCard({ project, onAction }: ProjectCardProps) {
  const {
    id,
    title,
    profileLabel,
    deadline,
    progressPercent,
    currentStep,
    lastEditedLabel,
    nextAction,
    warningBadge,
    analysisRunning,
  } = project

  const warningConfig = warningBadge ? WARNING_BADGE_CONFIG[warningBadge] : null

  // Whole card navigates to the same target as its next action; the button
  // below stays the accessible/keyboard path and stops propagation.
  const cardAction = analysisRunning ? "view_progress" : nextAction

  return (
    <Card
      className="flex cursor-pointer flex-col gap-0 overflow-hidden transition-colors hover:border-primary/40"
      onClick={() => onAction(id, cardAction)}
    >
      <CardHeader className="pb-3">
        {/* Warning badge — at most one, never shown when analysis is running */}
        {warningConfig && !analysisRunning && (
          <Badge
            variant="outline"
            className={cn("mb-2 self-start text-xs font-medium", warningConfig.className)}
          >
            {warningConfig.label}
          </Badge>
        )}

        <h2 className="text-balance text-base font-semibold leading-snug text-foreground">
          {title}
        </h2>
        <p className="text-xs text-muted-foreground">{profileLabel}</p>
        <p className="text-xs text-muted-foreground">{deadline}</p>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-4 pt-0">
        {/* Progress */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-foreground">
              {`Bearbeitungsstand: ${progressPercent}\u00a0%`}
            </span>
          </div>
          <Progress
            value={progressPercent}
            className="h-1.5"
            aria-label={`Bearbeitungsstand ${progressPercent} Prozent`}
          />
        </div>

        {/* Mini stepper summary */}
        <p className="text-xs text-muted-foreground">
          {`Schritt ${currentStep} von 8: ${getStepName(currentStep)}`}
        </p>

        {/* Last edited */}
        <p className="text-xs text-muted-foreground">{lastEditedLabel}</p>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Active analysis status line */}
        {analysisRunning && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin text-primary" aria-hidden />
            <span>Analyse läuft…</span>
          </div>
        )}

        {/* Next-action button — exactly one */}
        <Button
          variant={analysisRunning ? "outline" : "default"}
          className="w-full"
          onClick={(e) => {
            e.stopPropagation()
            onAction(id, cardAction)
          }}
        >
          {analysisRunning ? "Fortschritt ansehen" : NEXT_ACTION_LABELS[nextAction]}
        </Button>
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Step name helper — uses the 8 step labels from mock-data.
// Avoids importing the full workflowSteps array to keep this component lean.
// ---------------------------------------------------------------------------
const STEP_NAMES: Record<number, string> = {
  1: "Intake",
  2: "Quellen",
  3: "Anforderung",
  4: "Evidenz",
  5: "Entwurf",
  6: "Review",
  7: "Abschluss",
  8: "Export",
}

function getStepName(step: number): string {
  return STEP_NAMES[step] ?? `Schritt ${step}`
}
