import { Blend, Ruler, Sparkles, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  AVAILABILITY_LABELS,
  MODE_LABELS,
  type KiTeamRole,
  type RoleMode,
} from "@/lib/ki-team-data"

const MODE_ICONS: Record<RoleMode, LucideIcon> = {
  ki: Sparkles,
  regelbasiert: Ruler,
  hybrid: Blend,
}

const MODE_TINT: Record<RoleMode, string> = {
  ki: "border-primary/25 bg-primary/10 text-primary",
  regelbasiert: "border-border bg-muted text-foreground/75",
  hybrid: "border-primary/20 bg-primary/5 text-foreground/80",
}

export function ModeBadge({
  mode,
  className,
}: Readonly<{
  mode: RoleMode
  className?: string
}>) {
  const Icon = MODE_ICONS[mode]
  return (
    <span
      className={cn(
        "inline-flex min-h-6 w-fit shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium leading-none whitespace-nowrap",
        MODE_TINT[mode],
        className
      )}
    >
      <Icon aria-hidden="true" className="size-3.5" />
      {MODE_LABELS[mode]}
    </span>
  )
}

export function AvailabilityBadge({
  role,
  className,
}: Readonly<{
  role: KiTeamRole
  className?: string
}>) {
  if (role.availability === "available") return null
  return (
    <span
      className={cn(
        "inline-flex min-h-6 w-fit shrink-0 items-center rounded-full border border-status-partial/35 bg-status-partial/10 px-2.5 py-1 text-xs font-medium leading-none whitespace-nowrap text-status-partial",
        className
      )}
    >
      {AVAILABILITY_LABELS[role.availability]}
    </span>
  )
}
