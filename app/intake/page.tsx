import { AppShell } from "@/components/shell/app-shell"
import { IntakeForm } from "@/components/intake/intake-form"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"

export default function IntakePage() {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
    >
      <IntakeForm />
    </AppShell>
  )
}
