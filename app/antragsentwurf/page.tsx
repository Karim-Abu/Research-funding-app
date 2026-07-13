"use client"

// DEMO.1 — "KI-Antragsentwurf" page: demo DraftPackage view + read-only real-run
// artifacts. Live mode only; the mock mode shows a friendly hint instead.

import { AppShell } from "@/components/shell/app-shell"
import { DraftPackageView } from "@/components/antragsentwurf/draft-package-view"
import { RealRunArtifacts } from "@/components/antragsentwurf/real-run-artifacts"
import { useSession } from "@/components/providers/app-providers"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"

function MockHint() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16 text-center">
      <p className="text-sm text-muted-foreground">
        Der KI-Antragsentwurf ist im Live-Modus verfügbar. Starten Sie die
        Anwendung mit angebundenem Backend, um den Demo-Entwurf zu erzeugen.
      </p>
    </div>
  )
}

export default function AntragsentwurfPage() {
  const { mode } = useSession()
  return (
    <AppShell user={currentUser} projects={projects} activeProjectId={activeProjectId}>
      {mode === "live" ? (
        <div className="flex flex-col gap-10 px-6 py-8">
          <DraftPackageView />
          <RealRunArtifacts />
        </div>
      ) : (
        <MockHint />
      )}
    </AppShell>
  )
}
