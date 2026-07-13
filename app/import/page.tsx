"use client"

// R3.3 — Import-Review-Seite («Bestehenden Innolink-Antrag hochladen»).
import { AppShell } from "@/components/shell/app-shell"
import { ImportReview } from "@/components/import/import-review"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"

export default function ImportPage() {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
    >
      <ImportReview />
    </AppShell>
  )
}
