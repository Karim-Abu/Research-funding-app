"use client"

import * as React from "react"
import { Plus, RefreshCw } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { ProjectCard } from "@/components/dashboard/project-card"
import {
  currentUser,
  dashboardProjects,
  projects,
  activeProjectId,
} from "@/lib/mock-data"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { NextAction } from "@/lib/types"

// The dashboard has no active workflow step — no stepper rendered.
type PageState = "loading" | "error" | "empty" | "default"

// Set to true only during internal prototyping — never in the evaluation view.
const showDebugControls = false

export default function DashboardPage() {
  // Start in "loading" for one second to demo the skeleton state, then
  // switch to "default". In a real app this would be driven by a data fetch.
  const [pageState, setPageState] = React.useState<PageState>("loading")

  React.useEffect(() => {
    const t = setTimeout(() => setPageState("default"), 1000)
    return () => clearTimeout(t)
  }, [])

  function handleAction(_projectId: string, _action: NextAction | "view_progress") {
    // Prototype — navigation would happen here.
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
              {`Willkommen zurück, ${currentUser.name.split(" ")[0]}`}
            </h1>
            <p className="text-sm text-muted-foreground">
              Arbeitsbereich Innosuisse-Anträge (Dummy-Daten)
            </p>
          </div>
          <Button>
            <Plus data-icon="inline-start" />
            Neuer Antrag
          </Button>
        </div>

        {/* Content area — four states */}
        {pageState === "loading" && <LoadingGrid />}
        {pageState === "error" && <ErrorState onRetry={() => setPageState("default")} />}
        {pageState === "empty" && <EmptyState />}
        {pageState === "default" && (
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {dashboardProjects.map((project) => (
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
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-16 text-center">
      <p className="text-sm text-muted-foreground">
        Noch keine Anträge. Starten Sie mit einem neuen Antrag.
      </p>
      <Button>
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
