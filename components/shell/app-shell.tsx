"use client"

import * as React from "react"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { WorkflowStepper } from "./workflow-stepper"
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

  return (
    <div className="flex h-screen min-w-[1280px] overflow-hidden bg-background">
      <Sidebar
        role={user.role}
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          user={user}
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
