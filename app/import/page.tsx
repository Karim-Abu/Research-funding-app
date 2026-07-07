"use client"

// R3.3 — Import-Review-Seite («Bestehenden Innolink-Antrag hochladen»).
import { AppShell } from "@/components/shell/app-shell"
import { ImportReview } from "@/components/import/import-review"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"

const importStepStatus = [
  "done",
  "current",
  "upcoming",
  "upcoming",
  "upcoming",
  "upcoming",
  "upcoming",
  "upcoming",
] as const

export default function ImportPage() {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
      currentStep={2}
      stepStatus={[...importStepStatus]}
    >
      <ImportReview />
    </AppShell>
  )
}
