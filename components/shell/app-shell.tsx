"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { WorkflowStepper } from "./workflow-stepper"
import { useSession } from "@/components/providers/app-providers"
import { WorkflowRunProvider } from "@/components/providers/workflow-run-provider"
import {
  getActiveProjectId,
  redactIntakeInSession,
  setActiveProjectId,
} from "@/lib/intake-store"
import { clearAllRichEditorSessionCache } from "@/lib/rich-editor-cache"
import { listProjects, toDashboardCard } from "@/lib/projects"
import { stepForPathname } from "@/lib/workflow"
import { PROJECT_STATUS_LABELS, type Project, type User } from "@/lib/types"

interface AppShellProps {
  user: User
  projects: Project[]
  activeProjectId: string
  /** "full" renders the horizontal step nav; "mini" renders the compact summary line. Defaults to "full". */
  stepperVariant?: "full" | "mini"
  children: React.ReactNode
}

const SIDEBAR_COLLAPSED_STORAGE_KEY = "rf_sidebar_collapsed"
const SIDEBAR_COMPACT_MEDIA_QUERY = "(max-width: 1023px)"

export function AppShell({
  user,
  projects,
  activeProjectId,
  stepperVariant = "full",
  children,
}: Readonly<AppShellProps>) {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = React.useState(false)
  const [projectId, setProjectId] = React.useState(activeProjectId)
  const [liveProjects, setLiveProjects] = React.useState<Project[] | null>(null)

  // In live mode the authenticated session user takes precedence over the
  // prop (mock identity); in mock mode the passed user is used unchanged.
  const { status, user: sessionUser, mode } = useSession()
  const effectiveUser: User =
    status === "authenticated" && sessionUser
      ? {
          name: sessionUser.name,
          displayRole: sessionUser.display_label ?? "",
          role: sessionUser.effective_role,
        }
      : user

  // Live mode: the shell resolves the real project list + the active Antrag
  // itself (sessionStorage), so every screen shows the same, correct context —
  // pages keep passing mock data for the mock mode only.
  React.useEffect(() => {
    if (mode !== "live") return
    let active = true
    listProjects()
      .then((items) => {
        if (!active) return
        setLiveProjects(
          items.map((p) => ({
            id: p.project_id,
            title: p.title,
            // Sidebar card status line — same derivation as the dashboard.
            statusLabel:
              PROJECT_STATUS_LABELS[
                toDashboardCard(p).cardStatus ?? "in_bearbeitung"
              ],
          }))
        )
      })
      .catch(() => {
        if (active) setLiveProjects([])
      })
    return () => {
      active = false
    }
  }, [mode])

  React.useEffect(() => {
    if (mode !== "live") return
    const stored = getActiveProjectId()
    if (stored) setProjectId(stored)
  }, [mode])

  React.useEffect(() => {
    try {
      const stored = globalThis.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY)
      if (stored === "true" || stored === "false") {
        setCollapsed(stored === "true")
        return
      }
      setCollapsed(
        globalThis.matchMedia?.(SIDEBAR_COMPACT_MEDIA_QUERY)?.matches ?? false
      )
    } catch {
      setCollapsed(false)
    }
  }, [])

  const shellProjects = mode === "live" ? (liveProjects ?? []) : projects
  const activeProject =
    shellProjects.find((p) => p.id === projectId) ?? null

  function handleSidebarToggle() {
    setCollapsed((current) => {
      const next = !current
      try {
        globalThis.localStorage.setItem(
          SIDEBAR_COLLAPSED_STORAGE_KEY,
          String(next)
        )
      } catch {
        // Keep the UI responsive even when browser storage is unavailable.
      }
      return next
    })
  }

  function handleProjectChange(id: string) {
    setProjectId(id)
    if (mode === "live") {
      setActiveProjectId(id)
      // Switching Antrag → drop the previous application's formatting cache.
      clearAllRichEditorSessionCache()
      // R4.4: das Intake gehört zum vorherigen Antrag — Inhalte leeren
      // (die Vertraulichkeitsstufe bleibt als restriktives Signal erhalten).
      redactIntakeInSession()
      // Screens read the active Antrag on mount — a full reload re-anchors
      // every open view to the newly selected application.
      globalThis.location.reload()
    }
  }

  return (
    <WorkflowRunProvider>
      <div className="flex h-screen min-w-0 overflow-hidden bg-background">
        <Sidebar
          collapsed={collapsed}
          onToggle={handleSidebarToggle}
          activeProjectTitle={activeProject?.title ?? null}
          activeProjectStatusLabel={activeProject?.statusLabel ?? null}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar
            user={effectiveUser}
            projects={shellProjects}
            activeProjectId={projectId}
            onProjectChange={handleProjectChange}
          />
          {/* Der Stepper erscheint auf allen Workflow-Routen — der aktuelle
              Schritt kommt aus der Route, die Statuswerte aus dem Provider. */}
          {stepForPathname(pathname) && (
            <WorkflowStepper variant={stepperVariant} />
          )}
          <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
        </div>
      </div>
    </WorkflowRunProvider>
  )
}
