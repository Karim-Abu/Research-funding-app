"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { Plus, RefreshCw } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { ProjectCard } from "@/components/dashboard/project-card"
import { ProjectSummaryBar } from "@/components/dashboard/project-summary"
import {
  currentUser,
  dashboardProjects,
  projects,
  activeProjectId,
} from "@/lib/mock-data"
import { useSession } from "@/components/providers/app-providers"
import { listProjects, toDashboardCard, withCanonicalStatus } from "@/lib/projects"
import { getReviewStatus } from "@/lib/status"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { setActiveProjectId } from "@/lib/intake-store"
import {
  filterAndSortProjects,
  PROJECT_FILTERS,
  type ProjectFilter,
  type ProjectSort,
} from "@/lib/dashboard"
import { cn } from "@/lib/utils"
import type { DashboardProject, NextAction } from "@/lib/types"

// The dashboard has no active workflow step — no stepper rendered.
type PageState = "loading" | "error" | "empty" | "default"

// Set to true only during internal prototyping — never in the evaluation view.
const showDebugControls = false

// Where each next action takes the user in the guided workflow.
const ACTION_ROUTES: Record<NextAction | "view_progress", string> = {
  upload_sources: "/quellen",
  start_analysis: "/quellen",
  review_analysis: "/anforderungen",
  // Beta: Review ist die einzige Editier-Oberfläche.
  continue_draft: "/editor",
  approve_review: "/review",
  create_export: "/export",
  resume_analysis: "/quellen",
  view_progress: "/quellen",
}

export default function DashboardPage() {
  const router = useRouter()
  const { mode, user } = useSession()
  const [pageState, setPageState] = React.useState<PageState>("loading")
  const [liveCards, setLiveCards] = React.useState<DashboardProject[]>([])

  const loadLive = React.useCallback(() => {
    let active = true
    setPageState("loading")
    listProjects()
      .then(async (items) => {
        const cards = items.map(toDashboardCard)
        // R1.3 — kanonischer Status je Projekt (eine Quelle, lib/status.ts):
        // die Dashboard-Blockerzahl kommt aus dem Status-View des letzten Runs,
        // nicht mehr aus der «run_stopped»-Heuristik.
        const enriched = await Promise.all(
          cards.map(async (card) => {
            if (!card.latestRunId) return card
            try {
              const status = await getReviewStatus(card.latestRunId)
              return withCanonicalStatus(card, status.blocker_count)
            } catch {
              return card
            }
          })
        )
        if (!active) return
        setLiveCards(enriched)
        setPageState(enriched.length > 0 ? "default" : "empty")
      })
      .catch(() => {
        if (active) setPageState("error")
      })
    return () => {
      active = false
    }
  }, [])

  React.useEffect(() => {
    // Mock mode: keep the brief skeleton demo. Live mode: fetch real projects.
    if (mode === "mock") {
      const t = setTimeout(() => setPageState("default"), 400)
      return () => clearTimeout(t)
    }
    return loadLive()
  }, [mode, loadLive])

  const cards = mode === "live" ? liveCards : dashboardProjects

  // Orientation controls — user-created projects are first-class; filters and
  // search replace any count-based assumptions about the project list.
  const [query, setQuery] = React.useState("")
  const [filter, setFilter] = React.useState<ProjectFilter>("alle")
  const [sort, setSort] = React.useState<ProjectSort>("neueste")
  const visibleCards = filterAndSortProjects(cards, { query, filter, sort })

  function handleAction(projectId: string, action: NextAction | "view_progress") {
    setActiveProjectId(projectId)
    router.push(ACTION_ROUTES[action])
  }

  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
    >
      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Header row */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold text-foreground text-balance">
              Projektübersicht
            </h1>
            <p className="text-sm text-muted-foreground">
              {`Willkommen zurück, ${(user?.name ?? currentUser.name).split(" ")[0]} — wählen Sie einen Antrag aus, um ihn zu bearbeiten.`}
            </p>
          </div>
          <Button onClick={() => router.push("/intake")}>
            <Plus data-icon="inline-start" />
            Neuer Antrag
          </Button>
        </div>

        {/* Compact overview — only when projects are loaded */}
        {pageState === "default" && cards.length > 0 && (
          <ProjectSummaryBar projects={cards} />
        )}

        {/* Search / filter / sort — orientation for any number of Anträge */}
        {pageState === "default" && cards.length > 0 && (
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Anträge durchsuchen…"
              aria-label="Anträge durchsuchen"
              className="h-9 w-64 rounded-md border border-border bg-card px-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
            />
            <fieldset className="m-0 flex flex-wrap items-center gap-1.5 border-0 p-0">
              <legend className="sr-only">Nach Status filtern</legend>
              {PROJECT_FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setFilter(f.id)}
                  aria-pressed={filter === f.id}
                  className={cn(
                    "inline-flex h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    filter === f.id
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-card text-foreground hover:bg-accent"
                  )}
                >
                  {f.label}
                </button>
              ))}
            </fieldset>
            <label className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
              <span>Sortierung</span>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as ProjectSort)}
                className="h-9 rounded-md border border-border bg-card px-2 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="neueste">Zuletzt angelegt</option>
                <option value="fortschritt">Fortschritt</option>
                <option value="titel">Titel</option>
              </select>
            </label>
          </div>
        )}

        {/* Content area — four states */}
        {pageState === "loading" && <LoadingGrid />}
        {pageState === "error" && (
          <ErrorState
            onRetry={mode === "live" ? loadLive : () => setPageState("default")}
          />
        )}
        {pageState === "empty" && <EmptyState />}
        {pageState === "default" && visibleCards.length === 0 && cards.length > 0 && (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-12 text-center">
            <p className="text-sm text-muted-foreground">
              Keine Anträge entsprechen der Suche oder dem Filter.
            </p>
            <Button
              variant="outline"
              onClick={() => {
                setQuery("")
                setFilter("alle")
              }}
            >
              Filter zurücksetzen
            </Button>
          </div>
        )}
        {pageState === "default" && visibleCards.length > 0 && (
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {visibleCards.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onAction={handleAction}
              />
            ))}
          </div>
        )}

        {/* State switcher — hidden from normal user-facing UI */}
        {showDebugControls && (
          <DebugStateSwitcher current={pageState} onChange={setPageState} />
        )}
      </div>
    </AppShell>
  )
}

// ---------------------------------------------------------------------------
// Loading state — 3 skeleton cards
// ---------------------------------------------------------------------------
function LoadingGrid() {
  return (
    <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5"
        >
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-5 w-4/5" />
          <Skeleton className="h-3 w-1/2" />
          <Skeleton className="h-1.5 w-full rounded-full" />
          <Skeleton className="h-3 w-2/5" />
          <Skeleton className="mt-auto h-9 w-full" />
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
function EmptyState() {
  const router = useRouter()
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-16 text-center">
      <p className="text-sm text-muted-foreground">
        Noch keine Anträge. Starten Sie mit einem neuen Antrag.
      </p>
      <Button onClick={() => router.push("/intake")}>
        <Plus data-icon="inline-start" />
        Neuer Antrag
      </Button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------
function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-16 text-center">
      <p className="text-sm text-muted-foreground">
        Anträge konnten nicht geladen werden. Bitte versuchen Sie es erneut.
      </p>
      <Button variant="outline" onClick={onRetry}>
        <RefreshCw data-icon="inline-start" />
        Erneut versuchen
      </Button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Debug state switcher — collapsed by default
// ---------------------------------------------------------------------------
import { ChevronDown, ChevronRight } from "lucide-react"

function DebugStateSwitcher({
  current,
  onChange,
}: {
  current: PageState
  onChange: (s: PageState) => void
}) {
  const [open, setOpen] = React.useState(false)
  const states: { id: PageState; label: string }[] = [
    { id: "default", label: "Standard (4 Anträge)" },
    { id: "loading", label: "Laden (Skeleton)" },
    { id: "empty", label: "Leer" },
    { id: "error", label: "Fehler" },
  ]

  return (
    <div className="mt-12 border-t border-border pt-6">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded text-xs font-medium text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        aria-expanded={open}
      >
        {open ? (
          <ChevronDown className="size-3.5" />
        ) : (
          <ChevronRight className="size-3.5" />
        )}
        Demo: Seitenzustände testen
      </button>
      {open && (
        <div className="mt-3 flex flex-wrap gap-2">
          {states.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onChange(s.id)}
              className={
                "inline-flex h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 " +
                (current === s.id
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-card text-foreground hover:bg-accent hover:text-accent-foreground")
              }
            >
              {s.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
