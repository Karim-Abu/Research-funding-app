// Presentation helpers for the Projekte overview. Pure functions over the
// existing DashboardProject shape — no backend calls, no API contract.

import type { DashboardProject, ProjectCardStatus } from "./types"

/** Tailwind classes per status, matching the app's status colour tokens. */
export const PROJECT_STATUS_BADGE: Record<
  ProjectCardStatus,
  { className: string }
> = {
  in_bearbeitung: {
    className: "bg-muted text-muted-foreground border-border",
  },
  review_offen: {
    className:
      "bg-status-partial/10 text-status-partial border-status-partial/20",
  },
  blockiert: {
    className: "bg-destructive/10 text-destructive border-destructive/20",
  },
  eingereicht: {
    className:
      "bg-status-fulfilled/10 text-status-fulfilled border-status-fulfilled/20",
  },
}

export interface ProjectSummary {
  activeCount: number
  reviewOpenCount: number
  blockerCount: number
  nextDeadlineLabel: string
}

function formatDeadline(iso: string): string {
  return new Date(iso).toLocaleDateString("de-CH", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

/** Aggregate the compact overview shown above the project grid. */
export function summarizeProjects(cards: DashboardProject[]): ProjectSummary {
  const activeCount = cards.filter((c) => c.cardStatus !== "eingereicht").length
  const reviewOpenCount = cards.filter(
    (c) => c.cardStatus === "review_offen"
  ).length
  const blockerCount = cards.filter((c) => c.cardStatus === "blockiert").length

  const upcoming = cards
    .map((c) => c.deadlineIso)
    .filter((iso): iso is string => Boolean(iso))
    .sort()
  const nextDeadlineLabel = upcoming.length > 0 ? formatDeadline(upcoming[0]) : "—"

  return { activeCount, reviewOpenCount, blockerCount, nextDeadlineLabel }
}
