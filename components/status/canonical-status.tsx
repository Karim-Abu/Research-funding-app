"use client"

// R1.3 — Kanonische Statusanzeige. Ein Badge, eine Quelle (lib/status.ts):
// dieselbe Blocker-Zahl auf Dashboard, Anforderungen, Qualitätsprüfung und
// Export. Farbinformation immer mit Textlabel.

import { OctagonAlert, CheckCircle2, Clock, CircleDashed } from "lucide-react"
import { cn } from "@/lib/utils"
import { useReviewStatus, STALE_LABEL } from "@/lib/status"

/** Ehrlicher Leerzustand: keine Prüfung durchgeführt ⇒ nie «0 Blocker»,
 *  sondern «Noch nicht geprüft» (Workflow-Regel 7). */
export function NotYetReviewedBadge({ className }: { className?: string }) {
  return (
    <span
      data-testid="not-yet-reviewed"
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground",
        className
      )}
    >
      <CircleDashed className="size-3.5" aria-hidden />
      Noch nicht geprüft
    </span>
  )
}

export function CanonicalStatusBadge({ runId }: { runId: string }) {
  const { status } = useReviewStatus(runId)
  if (!status) return null

  const blocked = status.blocker_count > 0
  return (
    <div
      data-testid="canonical-status"
      className="flex flex-wrap items-center gap-2"
    >
      <span
        data-testid="canonical-blocker-count"
        data-blocker-count={status.blocker_count}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
          blocked
            ? "border-destructive/20 bg-destructive/10 text-destructive"
            : "border-status-fulfilled/20 bg-status-fulfilled/10 text-status-fulfilled"
        )}
      >
        {blocked ? (
          <OctagonAlert className="size-3.5" aria-hidden />
        ) : (
          <CheckCircle2 className="size-3.5" aria-hidden />
        )}
        {status.blocker_count === 0
          ? "Keine Blocker offen"
          : `${status.blocker_count} Blocker offen`}
      </span>
      {status.stale && (
        <span
          data-testid="canonical-stale"
          className="inline-flex items-center gap-1.5 rounded-full border border-status-partial/20 bg-status-partial/10 px-2.5 py-0.5 text-xs font-medium text-status-partial"
        >
          <Clock className="size-3.5" aria-hidden />
          {STALE_LABEL}
        </span>
      )}
    </div>
  )
}
