"use client"

import { Info, AlertTriangle, ShieldAlert } from "lucide-react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"

export type CostStatus = "ok" | "warn" | "stopped"

interface CostStatusBarProps {
  status?: CostStatus
  kiOn?: boolean
  webOn?: boolean
}

/**
 * Fixed footer bar. Resting state shows no CHF numbers — only the Details popover does.
 * Becomes visually prominent only in warn/stopped variants.
 */
export function CostStatusBar({
  status = "ok",
  kiOn = true,
  webOn = false,
}: CostStatusBarProps) {
  if (status === "stopped") {
    return (
      <div className="flex h-12 shrink-0 items-center gap-2 border-t border-status-blocker/30 bg-status-blocker/10 px-4 text-sm font-medium text-status-blocker">
        <ShieldAlert className="size-4" />
        Durchlauf gestoppt: Kostenlimit erreicht. Bisherige Ergebnisse sind
        gespeichert.
      </div>
    )
  }

  if (status === "warn") {
    return (
      <div className="flex h-12 shrink-0 items-center gap-2 border-t border-status-partial/30 bg-status-partial/10 px-4 text-sm font-medium text-status-partial">
        <AlertTriangle className="size-4" />
        Limit fast erreicht
        <span className="text-status-partial/80">·</span>
        <CostDetails />
      </div>
    )
  }

  return (
    <div className="flex h-12 shrink-0 items-center gap-2 border-t border-border bg-card px-4 text-sm text-muted-foreground">
      <span>Limit OK</span>
      <span aria-hidden>·</span>
      <span>{`KI ${kiOn ? "an" : "aus"}`}</span>
      <span aria-hidden>·</span>
      <span>{`Webrecherche ${webOn ? "an" : "aus"}`}</span>
      <span aria-hidden>·</span>
      <CostDetails />
    </div>
  )
}

function CostDetails({ className }: { className?: string }) {
  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          "inline-flex items-center gap-1 rounded font-medium underline-offset-2 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring",
          className
        )}
      >
        <Info className="size-3.5" />
        Details
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72">
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold text-foreground">
            ~CHF 0.60 von CHF 2.00 (Dummy)
          </span>
          <span className="text-xs leading-relaxed text-muted-foreground">
            Schätzung — der automatische Stopp schützt Ihr Limit.
          </span>
        </div>
      </PopoverContent>
    </Popover>
  )
}
