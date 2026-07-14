"use client"

import * as React from "react"
import { Loader2, CalendarClock, MoreVertical, Trash2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { NotYetReviewedBadge } from "@/components/status/canonical-status"
import {
  NEXT_ACTION_LABELS,
  PROJECT_STATUS_BADGE,
  WARNING_BADGE_LABELS,
} from "@/lib/dashboard"
import { WORKFLOW_STEPS } from "@/lib/workflow"
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
  /** Entfernt die Karte aus der Übersicht (archiviert das Projekt). */
  onRemove: (projectId: string) => void
}

// Up to this many avatars are shown before collapsing into a "+N" count.
const MAX_AVATARS = 3

export function ProjectCard({ project, onAction, onRemove }: ProjectCardProps) {
  const [confirmOpen, setConfirmOpen] = React.useState(false)
  const {
    id,
    title,
    fundingProgram,
    applicationType,
    deadline,
    progressPercent,
    currentStep,
    cardStatus,
    lastEditedLabel,
    nextAction,
    warningBadge,
    analysisRunning,
    isDemo,
    people,
    openBlockerCount,
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
        <div className="mb-2 flex items-start justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
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
            {/* R1.3/B7 — kanonische Zahl «Blockierende Aufgaben»
                (ReviewStatusView); dieselbe Zahl wie in Anforderungen,
                Qualitätsprüfung und Export. Ohne durchgeführte Prüfung
                erscheint nie eine 0, sondern «Noch nicht geprüft» (Regel 7). */}
            {typeof openBlockerCount === "number" && openBlockerCount > 0 && (
              <Badge
                variant="outline"
                data-testid="card-blocker-count"
                data-blocker-count={openBlockerCount}
                className="border-destructive/20 bg-destructive/10 text-xs font-medium text-destructive"
              >
                {`${openBlockerCount} blockierende ${openBlockerCount === 1 ? "Aufgabe" : "Aufgaben"}`}
              </Badge>
            )}
            {typeof openBlockerCount !== "number" && <NotYetReviewedBadge />}
          </div>

          {/* Kartenaktionen — Kebab-Menü. stopPropagation, damit ein Klick nicht
              die Karten-Navigation auslöst (die ganze Karte ist klickbar). */}
          <DropdownMenu>
            <DropdownMenuTrigger
              aria-label="Aktionen"
              onClick={(e) => e.stopPropagation()}
              className={cn(
                buttonVariants({ variant: "ghost", size: "icon-sm" }),
                "-mr-1 shrink-0 text-muted-foreground"
              )}
            >
              <MoreVertical className="size-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-56"
              onClick={(e) => e.stopPropagation()}
            >
              <DropdownMenuItem
                variant="destructive"
                onClick={(e) => {
                  e.stopPropagation()
                  setConfirmOpen(true)
                }}
              >
                <Trash2 className="size-4" />
                Aus Übersicht entfernen
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
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
          {`Schritt ${currentStep} von ${WORKFLOW_STEPS.length}: ${getStepName(currentStep)}`}
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

      {/* Bestätigung vor dem Entfernen (Human-in-the-loop). Dialog liegt im
          Portal → stopPropagation verhindert die Karten-Navigation. */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent onClick={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Projekt aus Übersicht entfernen?</DialogTitle>
            <DialogDescription>
              {`„${title}“ wird archiviert und aus der Übersicht ausgeblendet. Die Daten bleiben erhalten.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Abbrechen
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setConfirmOpen(false)
                onRemove(id)
              }}
            >
              Entfernen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Step name helper — der EINE Workflow-Katalog liefert das Label; das
// Backend-Label (anderes Schrittmodell) wird bewusst nicht mehr durchgereicht.
// ---------------------------------------------------------------------------
function getStepName(step: number): string {
  return (
    WORKFLOW_STEPS.find((s) => s.step === step)?.label ?? `Schritt ${step}`
  )
}
