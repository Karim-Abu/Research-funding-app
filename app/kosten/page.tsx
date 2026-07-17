"use client"

import { AppShell } from "@/components/shell/app-shell"
import { KostenScreen } from "@/components/kosten/kosten-screen"
import { useSession } from "@/components/providers/app-providers"
import { currentUser, memberUser, projects, activeProjectId } from "@/lib/mock-data"
import type { Role } from "@/lib/types"

// Toggle to preview the member view (no pencil, no Dienste section).
const previewRole: Role = "lead_admin"

export default function KostenPage() {
  const { mode, user: sessionUser } = useSession()
  const role: Role =
    mode === "live" ? (sessionUser?.effective_role ?? "member") : previewRole
  const user = role === "lead_admin" ? currentUser : memberUser

  return (
    <AppShell
      user={user}
      projects={projects}
      activeProjectId={activeProjectId}
      // No stepper — this is not a workflow step.
    >
      <KostenScreen role={role} />
    </AppShell>
  )
}
