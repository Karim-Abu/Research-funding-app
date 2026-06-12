import { Lock, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  DATA_CLASS_LABELS,
  isCloudAllowed,
  type DataClass,
} from "@/lib/types"

interface DataClassBadgeProps {
  dataClass: DataClass
  className?: string
}

/**
 * Zeigt nach dem Intake dauerhaft, in welcher Vertraulichkeitsstufe
 * gearbeitet wird — und ob deshalb externe KI-/Webdienste laufen oder nicht.
 */
export function DataClassBadge({ dataClass, className }: DataClassBadgeProps) {
  const cloud = isCloudAllowed(dataClass)
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        cloud
          ? "border-border bg-muted/40 text-foreground"
          : "border-status-partial/40 bg-status-partial/8 text-foreground",
        className
      )}
    >
      {cloud ? (
        <Sparkles className="size-3.5 shrink-0 text-muted-foreground" />
      ) : (
        <Lock className="size-3.5 shrink-0 text-status-partial" />
      )}
      {DATA_CLASS_LABELS[dataClass]}
      <span className="text-muted-foreground">
        {cloud ? "· KI aktiv" : "· keine externen KI-/Webdienste"}
      </span>
    </span>
  )
}
