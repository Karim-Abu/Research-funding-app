"use client"

import * as React from "react"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import type { KiTeamRole, RoleMode } from "@/lib/ki-team-data"
import { ModeIcon, StatusChip, modeMatchesHighlight } from "./mode-badge"

interface RoleCardProps {
  role: KiTeamRole
  /** Eindeutig je Karten-Instanz (Rolle kann in mehreren Phasen erscheinen). */
  instanceId: string
  /** true → zeigt zusätzlich die kurze „Wann aktiv"-Zeile. */
  detailMode: boolean
  /** Aktiver Legenden-Modus für die Hervorhebung (oder null). */
  highlight: RoleMode | null
  /** Ob der Drawer für diese Karte gerade offen ist. */
  expanded: boolean
  onOpen: (role: KiTeamRole, instanceId: string, element: HTMLButtonElement) => void
}

/**
 * Eine Rolle als volle, klickbare Zeile: Modus-Icon + Name (ohne Abschneiden) +
 * optionaler Status-Chip + Chevron. Die ganze Zeile öffnet den Detail-Drawer.
 */
export function RoleCard({
  role,
  instanceId,
  detailMode,
  highlight,
  expanded,
  onOpen,
}: Readonly<RoleCardProps>) {
  const ref = React.useRef<HTMLButtonElement>(null)
  const highlighted = modeMatchesHighlight(role.mode, highlight)
  const dimmed = highlight !== null && !highlighted

  return (
    <button
      ref={ref}
      type="button"
      aria-haspopup="dialog"
      aria-expanded={expanded}
      onClick={() => {
        if (ref.current) onOpen(role, instanceId, ref.current)
      }}
      className={cn(
        "group/role flex w-full cursor-pointer items-center gap-3 rounded-lg border bg-card px-3 py-2 text-left outline-none transition-colors",
        "hover:border-primary/40 hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring",
        expanded
          ? "border-primary/50 bg-muted/40"
          : "border-border/70",
        highlighted && "border-primary/50 ring-2 ring-primary/25",
        dimmed && "opacity-45"
      )}
    >
      <ModeIcon mode={role.mode} />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-sm font-medium text-foreground">{role.name}</span>
          <StatusChip role={role} />
        </span>
        {detailMode && (
          <span className="mt-0.5 block text-xs text-muted-foreground">
            {role.aktiv}
          </span>
        )}
      </span>
      <ChevronRight
        aria-hidden="true"
        className="size-4 shrink-0 text-muted-foreground/60 transition-transform group-hover/role:translate-x-0.5"
      />
    </button>
  )
}
