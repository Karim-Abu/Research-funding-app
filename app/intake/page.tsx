import { AppShell } from "@/components/shell/app-shell"
import { IntakeForm } from "@/components/intake/intake-form"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"

const intakeStepStatus = [
  "current",
  "upcoming",
  "upcoming",
  "upcoming",
  "upcoming",
  "upcoming",
  "upcoming",
] as const

export default function IntakePage() {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={1}
      stepStatus={[...intakeStepStatus]}
    >
      <IntakeForm />
    </AppShell>
  )
}
