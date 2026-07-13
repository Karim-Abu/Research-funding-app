"use client"

import { AppShell } from "@/components/shell/app-shell"
import { KiTeamScreen } from "@/components/ki-team/ki-team-page"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"

export default function KiTeamPage() {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      // Kein Stepper — Transparenzseite, kein Workflow-Schritt.
    >
      <KiTeamScreen />
    </AppShell>
  )
}
