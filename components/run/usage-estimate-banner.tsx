import { Skeleton } from "@/components/ui/skeleton"

type EstimateState = "ready" | "loading" | "unavailable"

interface UsageEstimateBannerProps {
  state?: EstimateState
  /** Estimated amount in CHF (Dummy). */
  amount?: string
}

/** Estimate banner. Always includes the fixed protective-stop line. */
export function UsageEstimateBanner({
  state = "ready",
  amount = "0.40",
}: UsageEstimateBannerProps) {
  if (state === "loading") {
    return (
      <div className="flex flex-col gap-2 rounded-md border border-border bg-muted/40 p-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-64" />
      </div>
    )
  }

  if (state === "unavailable") {
    return (
      <div className="rounded-md border border-border bg-muted/40 p-3">
        <p className="text-sm text-muted-foreground">
          Schätzung nicht verfügbar — Limits und automatischer Stopp gelten
          weiterhin.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-muted/40 p-3">
      <span className="text-sm font-medium text-foreground">
        {`Geschätzt: ~CHF ${amount} (Dummy)`}
      </span>
      <span className="text-xs text-muted-foreground">
        Schätzung — der automatische Stopp schützt Ihr Limit.
      </span>
    </div>
  )
}
