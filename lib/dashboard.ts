// Presentation helpers for the Projekte overview. Pure functions over the
// existing DashboardProject shape — no backend calls, no API contract.

import type {
  DashboardProject,
  NextAction,
  ProjectCardStatus,
  WarningBadge,
} from "./types"

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

/** User-facing warning chips (text labels — never colour-only). */
export const WARNING_BADGE_LABELS: Record<WarningBadge, string> = {
  durchlauf_gestoppt: "Analyse gestoppt",
  freigabe_offen: "Freigabe offen",
}

/** "Nächster Schritt" line per next action — answers "what should I do?". */
export const NEXT_ACTION_LABELS: Record<NextAction | "view_progress", string> = {
  upload_sources: "Quellen hochladen",
  start_analysis: "Analyse starten",
  review_analysis: "Analyse & Anforderungen prüfen",
  continue_draft: "Entwurf weiterbearbeiten",
  approve_review: "Qualitätsprüfung abschließen",
  create_export: "Export erstellen",
  resume_analysis: "Analyse fortsetzen",
  view_progress: "Analyse läuft — Fortschritt ansehen",
}

export type ProjectFilter = "alle" | ProjectCardStatus | "demo"
export type ProjectSort = "neueste" | "fortschritt" | "titel"

export const PROJECT_FILTERS: { id: ProjectFilter; label: string }[] = [
  { id: "alle", label: "Alle" },
  { id: "in_bearbeitung", label: "In Bearbeitung" },
  { id: "review_offen", label: "Review offen" },
  { id: "blockiert", label: "Blockiert" },
  { id: "demo", label: "Demo" },
]

/** Client-side search + filter + sort. User-created projects are first-class;
 *  orientation comes from filters, never from count-based warnings. */
export function filterAndSortProjects(
  cards: DashboardProject[],
  opts: { query: string; filter: ProjectFilter; sort: ProjectSort }
): DashboardProject[] {
  const q = opts.query.trim().toLowerCase()
  let out = cards.filter((c) => {
    if (q && !c.title.toLowerCase().includes(q)) return false
    if (opts.filter === "alle") return true
    if (opts.filter === "demo") return Boolean(c.isDemo)
    return (c.cardStatus ?? "in_bearbeitung") === opts.filter
  })
  if (opts.sort === "fortschritt") {
    out = [...out].sort((a, b) => b.progressPercent - a.progressPercent)
  } else if (opts.sort === "titel") {
    out = [...out].sort((a, b) => a.title.localeCompare(b.title, "de"))
  }
  // "neueste" keeps the API order (newest first from the backend).
  return out
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
