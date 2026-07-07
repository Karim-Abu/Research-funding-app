// R1.3 — Kanonischer Status-Client. EINZIGER Frontend-Zugang zum R1.2-Status-View
// (GET /api/runs/{id}/review/status). Dashboard, Anforderungen, Qualitätsprüfung
// und Export lesen ihre Blocker-/Stale-Anzeige aus dieser einen Quelle; keine
// Screen-eigene Blocker-Zählung mehr.

import * as React from "react"

export interface ReviewStatusDto {
  run_id: string
  blocker_count: number
  warning_count: number
  human_review_count: number
  stale: boolean
  approval_status: "open" | "blocked" | "approved" | "changes_required" | "stale"
  review_package_version: string
  per_area_counts: Record<string, number>
  last_reviewed_at: string | null
}

/** Einheitlicher Stale-Wortlaut auf allen Screens (R1.3). */
export const STALE_LABEL = "Prüfung nicht aktuell"

export async function getReviewStatus(runId: string): Promise<ReviewStatusDto> {
  const res = await fetch(
    `/api/runs/${encodeURIComponent(runId)}/review/status`
  )
  if (!res.ok) {
    throw new Error("Der Prüfstatus konnte nicht geladen werden.")
  }
  return (await res.json()) as ReviewStatusDto
}

/** Status-Hook: lädt den kanonischen Status eines Runs; `reload` nach Aktionen
 *  (Recheck, Freigabe, Feld-Edit) aufrufen. */
export function useReviewStatus(runId: string | null | undefined): {
  status: ReviewStatusDto | null
  error: string | null
  reload: () => void
} {
  const [status, setStatus] = React.useState<ReviewStatusDto | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const reload = React.useCallback(() => {
    if (!runId) {
      setStatus(null)
      return
    }
    getReviewStatus(runId)
      .then((s) => {
        setStatus(s)
        setError(null)
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Status nicht ladbar.")
      )
  }, [runId])

  React.useEffect(() => reload(), [reload])
  return { status, error, reload }
}
