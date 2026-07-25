"use client"

import { AppShell } from "@/components/shell/app-shell"
import { KostenScreen } from "@/components/kosten/kosten-screen"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"

export default function KostenPage() {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      // No stepper — this is not a workflow step.
    >
      <KostenScreen />
    </AppShell>
  )
}
