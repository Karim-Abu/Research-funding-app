"use client"

import { FolderKanban, ClipboardCheck, OctagonAlert, CalendarClock } from "lucide-react"
import { cn } from "@/lib/utils"
import { summarizeProjects } from "@/lib/dashboard"
import type { DashboardProject } from "@/lib/types"

interface ProjectSummaryBarProps {
  projects: DashboardProject[]
}

/** Compact overview row above the project grid. Counts are derived in the frontend. */
export function ProjectSummaryBar({ projects }: ProjectSummaryBarProps) {
  const summary = summarizeProjects(projects)

  const tiles: {
    label: string
    value: string | number
    icon: typeof FolderKanban
    accent?: string
  }[] = [
    { label: "Aktive Projekte", value: summary.activeCount, icon: FolderKanban },
    {
      label: "Review offen",
      value: summary.reviewOpenCount,
      icon: ClipboardCheck,
      accent: summary.reviewOpenCount > 0 ? "text-status-partial" : undefined,
    },
    {
      label: "Blocker",
      value: summary.blockerCount,
      icon: OctagonAlert,
      accent: summary.blockerCount > 0 ? "text-destructive" : undefined,
    },
    {
      label: "Nächste Frist",
      value: summary.nextDeadlineLabel,
      icon: CalendarClock,
    },
  ]

  return (
    <dl className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((tile) => (
        <div
          key={tile.label}
          className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3"
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
            <tile.icon className="size-4" aria-hidden />
          </span>
          <div className="flex min-w-0 flex-col">
            <dt className="truncate text-xs text-muted-foreground">{tile.label}</dt>
            <dd className={cn("text-lg font-semibold text-foreground", tile.accent)}>
              {tile.value}
            </dd>
          </div>
        </div>
      ))}
    </dl>
  )
}
