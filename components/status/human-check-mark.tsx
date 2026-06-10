import { UserCheck } from "lucide-react"
import { cn } from "@/lib/utils"
import type { HumanCheck } from "@/lib/types"

interface HumanCheckMarkProps {
  check: HumanCheck
  className?: string
}

/**
 * Human confirmation — teal check with name + timestamp.
 * Visually distinct from machine status badges (never green).
 */
export function HumanCheckMark({ check, className }: HumanCheckMarkProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-human/30 bg-human/8 px-2 py-0.5 text-xs font-medium text-human",
        className
      )}
    >
      <UserCheck className="size-3.5" />
      {`Geprüft von ${check.name} · ${check.timestamp}`}
    </span>
  )
}
