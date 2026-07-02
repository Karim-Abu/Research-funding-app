"use client"

import * as React from "react"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { WorkflowStepper } from "./workflow-stepper"
import { useSession } from "@/components/providers/app-providers"
import { getActiveProjectId, setActiveProjectId } from "@/lib/intake-store"
import { listProjects } from "@/lib/projects"
import type { Project, StepStatus, User } from "@/lib/types"

interface AppShellProps {
  user: User
  projects: Project[]
  activeProjectId: string
  /** When provided, renders the WorkflowStepper under the topbar. */
  currentStep?: number
  stepStatus?: StepStatus[]
  /** "full" renders the horizontal step nav; "mini" renders the compact summary line. Defaults to "full". */
  stepperVariant?: "full" | "mini"
  children: React.ReactNode
}

export function AppShell({
  user,
  projects,
  activeProjectId,
  currentStep,
  stepStatus,
  stepperVariant = "full",
  children,
}: AppShellProps) {
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
        setLiveProjects(items.map((p) => ({ id: p.project_id, title: p.title })))
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

  const shellProjects = mode === "live" ? (liveProjects ?? []) : projects
  const activeProject =
    shellProjects.find((p) => p.id === projectId) ?? null

  function handleProjectChange(id: string) {
    setProjectId(id)
    if (mode === "live") {
      setActiveProjectId(id)
      // Screens read the active Antrag on mount — a full reload re-anchors
      // every open view to the newly selected application.
      window.location.reload()
    }
  }

  return (
    <div className="flex h-screen min-w-[1280px] overflow-hidden bg-background">
      <Sidebar
        role={effectiveUser.role}
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
        activeProjectTitle={activeProject?.title ?? null}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          user={effectiveUser}
          projects={shellProjects}
          activeProjectId={projectId}
          onProjectChange={handleProjectChange}
        />
        {currentStep && stepStatus && (
          <WorkflowStepper
            currentStep={currentStep}
            stepStatus={stepStatus}
            variant={stepperVariant}
          />
        )}
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}
