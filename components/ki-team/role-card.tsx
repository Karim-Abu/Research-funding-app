"use client"

import * as React from "react"
import {
  Calculator,
  ChevronRight,
  ClipboardCheck,
  FileOutput,
  FileSearch,
  Link2,
  ListChecks,
  PenLine,
  Search,
  ShieldCheck,
  Workflow,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { KiTeamRole, RoleIconKey } from "@/lib/ki-team-data"
import { AvailabilityBadge, ModeBadge } from "./mode-badge"

const ROLE_ICONS: Record<RoleIconKey, LucideIcon> = {
  workflow: Workflow,
  shieldCheck: ShieldCheck,
  search: Search,
  fileSearch: FileSearch,
  link2: Link2,
  penLine: PenLine,
  calculator: Calculator,
  listChecks: ListChecks,
  clipboardCheck: ClipboardCheck,
  fileOutput: FileOutput,
}

function iconTone(role: KiTeamRole): string {
  if (role.id === "suchanfragen-schutz") {
    return "border-status-fulfilled/25 bg-status-fulfilled/10 text-status-fulfilled"
  }
  if (role.category === "system") {
    return "border-border bg-muted text-foreground/70"
  }
  return "border-primary/20 bg-primary/8 text-primary"
}

export function RoleIcon({
  role,
  className,
}: Readonly<{ role: KiTeamRole; className?: string }>) {
  const Icon = ROLE_ICONS[role.iconKey]
  return (
    <span
      className={cn(
        "inline-flex size-10 shrink-0 items-center justify-center rounded-lg border",
        iconTone(role),
        className
      )}
    >
      <Icon aria-hidden="true" className="size-5" />
    </span>
  )
}

interface RoleCardProps {
  role: KiTeamRole
  instanceId: string
  expanded: boolean
  variant?: "row" | "catalog"
  onOpen: (
    role: KiTeamRole,
    instanceId: string,
    element: HTMLButtonElement
  ) => void
}

export function RoleCard({
  role,
  instanceId,
  expanded,
  variant = "row",
  onOpen,
}: Readonly<RoleCardProps>) {
  const ref = React.useRef<HTMLButtonElement>(null)
  const catalog = variant === "catalog"

  return (
    <button
      ref={ref}
      type="button"
      aria-haspopup="dialog"
      aria-expanded={expanded}
      aria-label={`${role.name}: ${role.specialization}. Details öffnen`}
      onClick={() => {
        if (ref.current) onOpen(role, instanceId, ref.current)
      }}
      className={cn(
        "group/role flex w-full cursor-pointer gap-3 text-left outline-none transition-[background-color,border-color,box-shadow] duration-200",
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        catalog
          ? "min-h-44 items-start rounded-xl border border-border bg-card p-5 hover:border-primary/30 hover:bg-muted/25"
          : "min-h-11 items-center rounded-lg px-3 py-3 hover:bg-background/80",
        expanded && "bg-accent/55 ring-2 ring-primary/20"
      )}
    >
      <RoleIcon role={role} />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-foreground">
            {role.name}
          </span>
          <ModeBadge mode={role.mode} />
          <AvailabilityBadge role={role} />
        </span>
        <span className="mt-1.5 block text-sm leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">Wobei hilft sie?</span>{" "}
          {role.specialization}
        </span>
        {catalog && (
          <span className="mt-3 block border-t border-border/70 pt-3 text-sm text-foreground">
            <span className="font-medium">Was erhalten Sie?</span>{" "}
            {role.outputSummary}
          </span>
        )}
      </span>
      <ChevronRight
        aria-hidden="true"
        className={cn(
          "size-4 shrink-0 text-muted-foreground/70 transition-transform duration-200 group-hover/role:translate-x-0.5",
          catalog ? "mt-3" : ""
        )}
      />
    </button>
  )
}
