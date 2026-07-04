"use client"

import { Loader2, CalendarClock } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import {
  Avatar,
  AvatarFallback,
  AvatarGroup,
  AvatarGroupCount,
} from "@/components/ui/avatar"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import {
  NEXT_ACTION_LABELS,
  PROJECT_STATUS_BADGE,
  WARNING_BADGE_LABELS,
} from "@/lib/dashboard"
import { workflowSteps } from "@/lib/mock-data"
import {
  PROJECT_STATUS_LABELS,
  type DashboardProject,
  type NextAction,
  type ProjectCardStatus,
} from "@/lib/types"

// ---------------------------------------------------------------------------
// ProjectCard
// ---------------------------------------------------------------------------
interface ProjectCardProps {
  project: DashboardProject
  onAction: (projectId: string, action: NextAction | "view_progress") => void
}

// Up to this many avatars are shown before collapsing into a "+N" count.
const MAX_AVATARS = 3

export function ProjectCard({ project, onAction }: ProjectCardProps) {
  const {
    id,
    title,
    fundingProgram,
    applicationType,
    deadline,
    progressPercent,
    currentStep,
    currentStepLabel,
    cardStatus,
    lastEditedLabel,
    nextAction,
    warningBadge,
    analysisRunning,
    isDemo,
    people,
  } = project

  const status: ProjectCardStatus = cardStatus ?? "in_bearbeitung"
  const program = fundingProgram ?? "Innosuisse"
  const type = applicationType ?? "Innovationsprojekt"
  const involved = people ?? []

  // Whole card navigates to the same target as its primary action; the button
  // below stays the accessible/keyboard path and stops propagation.
  const cardAction = analysisRunning ? "view_progress" : nextAction

  return (
    <Card
      className="flex cursor-pointer flex-col gap-0 overflow-hidden transition-colors hover:border-primary/40"
      onClick={() => onAction(id, cardAction)}
    >
      <CardHeader className="pb-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Badge
            variant="outline"
            className={cn(
              "text-xs font-medium",
              PROJECT_STATUS_BADGE[status].className
            )}
          >
            {PROJECT_STATUS_LABELS[status]}
          </Badge>
          {isDemo && (
            <Badge variant="secondary" className="text-xs font-medium">
              Demo
            </Badge>
          )}
          {warningBadge && (
            <Badge
              variant="outline"
              className="border-destructive/20 bg-destructive/10 text-xs font-medium text-destructive"
            >
              {WARNING_BADGE_LABELS[warningBadge]}
            </Badge>
          )}
        </div>

        <h2 className="text-balance text-base font-semibold leading-snug text-foreground">
          {title}
        </h2>
        <p className="text-xs text-muted-foreground">
          {program} · {type}
        </p>
        <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
          <CalendarClock className="size-3.5" aria-hidden />
          {deadline}
        </p>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-4 pt-0">
        {/* Bearbeitungsstand */}
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-foreground">
            {`Bearbeitungsstand: ${progressPercent} %`}
          </span>
          <Progress
            value={progressPercent}
            className="h-1.5"
            aria-label={`Bearbeitungsstand ${progressPercent} Prozent`}
          />
        </div>

        {/* Aktueller Schritt */}
        <p className="text-xs text-muted-foreground">
          {`Schritt ${currentStep} von 8: ${getStepName(
            currentStep,
            currentStepLabel
          )}`}
        </p>

        {/* Nächster Schritt — answers "what should I do next?" without
            changing the stable primary-button label. */}
        <p className="text-xs font-medium text-foreground">
          {`Nächster Schritt: ${NEXT_ACTION_LABELS[cardAction]}`}
        </p>

        {/* Letzte Aktivität */}
        <p className="text-xs text-muted-foreground">{lastEditedLabel}</p>

        {/* Active analysis status line */}
        {analysisRunning && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin text-primary" aria-hidden />
            <span>Analyse läuft…</span>
          </div>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Beteiligte Personen */}
        {involved.length > 0 && (
          <div className="flex items-center gap-2">
            <AvatarGroup>
              {involved.slice(0, MAX_AVATARS).map((person) => (
                <Tooltip key={person.name}>
                  <TooltipTrigger
                    render={
                      <Avatar size="sm">
                        <AvatarFallback>{person.initials}</AvatarFallback>
                      </Avatar>
                    }
                  />
                  <TooltipContent>{person.name}</TooltipContent>
                </Tooltip>
              ))}
              {involved.length > MAX_AVATARS && (
                <AvatarGroupCount className="size-6 text-xs">
                  {`+${involved.length - MAX_AVATARS}`}
                </AvatarGroupCount>
              )}
            </AvatarGroup>
            <span className="text-xs text-muted-foreground">
              {`${involved.length} beteiligt`}
            </span>
          </div>
        )}

        {/* Primäraktion — genau eine */}
        <Button
          variant={analysisRunning ? "outline" : "default"}
          className="w-full"
          onClick={(e) => {
            e.stopPropagation()
            onAction(id, cardAction)
          }}
        >
          Weiterarbeiten
        </Button>
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Step name helper — use the canonical workflow labels, with live backend labels
// as an optional frontend-only override.
// ---------------------------------------------------------------------------
function getStepName(step: number, label?: string | null): string {
  const workflowStep = workflowSteps.find((s) => s.step === step)
  return label ?? workflowStep?.shortLabel ?? workflowStep?.label ?? `Schritt ${step}`
}
