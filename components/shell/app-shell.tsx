"use client"

import * as React from "react"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { WorkflowStepper } from "./workflow-stepper"
import { useSession } from "@/components/providers/app-providers"
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

  // In live mode the authenticated session user takes precedence over the
  // prop (mock identity); in mock mode the passed user is used unchanged.
  const { status, user: sessionUser } = useSession()
  const effectiveUser: User =
    status === "authenticated" && sessionUser
      ? {
          name: sessionUser.name,
          displayRole: sessionUser.display_label ?? "",
          role: sessionUser.effective_role,
        }
      : user

  return (
    <div className="flex h-screen min-w-[1280px] overflow-hidden bg-background">
      <Sidebar
        role={effectiveUser.role}
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          user={effectiveUser}
          projects={projects}
          activeProjectId={projectId}
          onProjectChange={setProjectId}
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
