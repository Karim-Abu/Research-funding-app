"use client"

import * as React from "react"
import { AppShell } from "@/components/shell/app-shell"
import { KostenScreen } from "@/components/kosten/kosten-screen"
import { currentUser, memberUser, projects, activeProjectId } from "@/lib/mock-data"
import type { Role } from "@/lib/types"

// Toggle to preview the member view (no pencil, no Dienste section).
const previewRole: Role = "lead_admin"

export default function KostenPage() {
  const user = previewRole === "lead_admin" ? currentUser : memberUser

  return (
    <AppShell
      user={user}
      projects={projects}
      activeProjectId={activeProjectId}
      // No stepper — this is not a workflow step.
    >
      <KostenScreen role={previewRole} />
    </AppShell>
  )
}
