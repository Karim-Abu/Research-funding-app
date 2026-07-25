"use client"

import { AppShell } from "@/components/shell/app-shell"
import { SystemStatusScreen } from "@/components/system-status/system-status-screen"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"

export default function SystemStatusPage() {
  return (
    <AppShell user={currentUser} projects={projects} activeProjectId={activeProjectId}>
      <SystemStatusScreen />
    </AppShell>
  )
}
