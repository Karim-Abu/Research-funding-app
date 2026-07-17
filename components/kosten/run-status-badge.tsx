import {
  Ban,
  CheckCircle2,
  OctagonX,
  XCircle,
  type LucideIcon,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { RUN_STATUS_LABELS, type KostenRunStatus } from "@/lib/kosten"
import { cn } from "@/lib/utils"

const STATUS_STYLE: Record<
  KostenRunStatus,
  { icon: LucideIcon; className: string }
> = {
  completed: {
    icon: CheckCircle2,
    className:
      "border-status-fulfilled/40 bg-status-fulfilled/10 text-status-fulfilled",
  },
  stopped_cost: {
    icon: OctagonX,
    className:
      "border-status-partial/40 bg-status-partial/10 text-status-partial",
  },
  failed: {
    icon: XCircle,
    className: "border-destructive/40 bg-destructive/10 text-destructive",
  },
  cancelled: {
    icon: Ban,
    className: "border-muted-foreground/30 bg-muted text-muted-foreground",
  },
}

export function RunStatusBadge({
  status,
  className,
}: {
  status: KostenRunStatus
  className?: string
}) {
  const config = STATUS_STYLE[status]
  const Icon = config.icon
  return (
    <Badge
      variant="outline"
      className={cn("h-auto py-1", config.className, className)}
    >
      <Icon aria-hidden className="size-3" />
      {RUN_STATUS_LABELS[status]}
    </Badge>
  )
}
