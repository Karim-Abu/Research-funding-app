import { CheckCircle2, AlertTriangle, Circle, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import type { MachineStatus } from "@/lib/types"

const config: Record<
  MachineStatus,
  { label: string; className: string; icon: typeof CheckCircle2 }
> = {
  verified: {
    label: "Verifiziert",
    className: "bg-status-fulfilled/12 text-status-fulfilled",
    icon: CheckCircle2,
  },
  partial: {
    label: "Prüfen",
    className: "bg-status-partial/12 text-status-partial",
    icon: AlertTriangle,
  },
  open: {
    label: "Offen",
    className: "bg-muted text-muted-foreground",
    icon: Circle,
  },
  blocker: {
    label: "Blockierend",
    className: "bg-status-blocker/12 text-status-blocker",
    icon: XCircle,
  },
}

interface MachineStatusBadgeProps {
  status: MachineStatus
  /** Override the default German label. */
  label?: string
  className?: string
}

/** Machine-evaluated status. Always a colored badge — never used for human checks. */
export function MachineStatusBadge({
  status,
  label,
  className,
}: MachineStatusBadgeProps) {
  const c = config[status]
  const Icon = c.icon
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        c.className,
        className
      )}
    >
      <Icon className="size-3.5" />
      {label ?? c.label}
    </span>
  )
}
