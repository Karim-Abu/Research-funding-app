import { AppShell } from "@/components/shell/app-shell"
import { RequirementsScreen } from "@/components/anforderungen/requirements-screen"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"

const stepStatus = [
  "done",
  "done",
  "current",
  "todo",
  "todo",
  "todo",
  "todo",
  "todo",
] as const

export default function AnforderungenPage() {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={3}
      stepStatus={[...stepStatus]}
    >
      <RequirementsScreen />
    </AppShell>
  )
}
