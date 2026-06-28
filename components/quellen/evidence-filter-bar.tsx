"use client"

import { cn } from "@/lib/utils"
import {
  EVIDENCE_FILTER_LABELS,
  type EvidenceFilter,
  type EvidenceStatusFilter,
} from "@/lib/evidence"

interface EvidenceFilterBarProps {
  /** Status chips to render — pass only the statuses that actually occur. */
  available: EvidenceStatusFilter[]
  /** Show the "Ohne genaue Fundstelle" chip. */
  showNoLocation: boolean
  value: EvidenceFilter
  onChange: (value: EvidenceFilter) => void
}

// Stable display order regardless of which statuses are present.
const STATUS_ORDER: EvidenceStatusFilter[] = ["verified", "review", "open", "error"]

/** Simple, calm filter chips shared by the Mock and Live evidence views. */
export function EvidenceFilterBar({
  available,
  showNoLocation,
  value,
  onChange,
}: EvidenceFilterBarProps) {
  const chips: EvidenceFilter[] = [
    "all",
    ...STATUS_ORDER.filter((s) => available.includes(s)),
    ...(showNoLocation ? (["no_location"] as const) : []),
  ]

  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Belege filtern">
      {chips.map((chip) => {
        const active = value === chip
        return (
          <button
            key={chip}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(chip)}
            className={cn(
              "inline-flex h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              active
                ? "border-primary bg-primary/10 text-primary"
                : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            )}
          >
            {EVIDENCE_FILTER_LABELS[chip]}
          </button>
        )
      })}
    </div>
  )
}
