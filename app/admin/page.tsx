"use client"

import Link from "next/link"
import { AppShell } from "@/components/shell/app-shell"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import { LiveSystemStatus } from "@/components/admin/live-system-status"

// Evaluation & Technik — Hub für technische Demo-/Evaluationsansichten
// (Provider, Modelle, Tokens, Kosten, synthetische Läufe, missing_inputs).
// Diese Inhalte gehören bewusst NICHT in den geführten Antrags-Workflow;
// der normale Nutzerpfad zeigt technische Details nur eingeklappt unter
// «Technische Details» (R6, Kopieransicht-Regel 6/7).
const EVAL_VIEWS = [
  {
    href: "/antragsentwurf",
    title: "KI-Antragsentwurf (Evaluationsansicht)",
    description:
      "Integrierter Entwurf über alle unterstützten Felder mit technischen " +
      "Angaben zu Provider, Modell, Tokens, Kosten und fehlenden Eingaben. " +
      "Für Evaluation und Demo — nicht Teil des Antrags-Workflows.",
  },
  {
    href: "/kosten",
    title: "Kosten & Laufzeit (Demo)",
    description:
      "Demo-Ansicht zu Kosten- und Laufzeitdaten. Nutzt synthetische " +
      "Beispieldaten, keine Antragsentscheidung.",
  },
] as const

export default function Page() {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
    >
      <div className="mx-auto flex max-w-3xl flex-col gap-5 px-6 py-8">
        <div>
          <h1 className="text-lg font-semibold">Evaluation &amp; Technik</h1>
          <p className="text-sm text-muted-foreground">
            Technische Ansichten für Evaluation, Demo und Betreuung. Im
            normalen Antragsablauf erscheinen technische Daten nur eingeklappt
            unter «Technische Details».
          </p>
        </div>
        <LiveSystemStatus />
        <ul className="flex flex-col gap-3">
          {EVAL_VIEWS.map((view) => (
            <li key={view.href}>
              <Link
                href={view.href}
                className="flex flex-col gap-1 rounded-lg border border-border bg-card px-4 py-3 outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="text-sm font-semibold text-foreground">
                  {view.title}
                </span>
                <span className="text-xs text-muted-foreground">
                  {view.description}
                </span>
              </Link>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted-foreground">
          Hinweis: Auch diese Ansichten übertragen nichts automatisch nach
          Innolink und treffen keine Förderentscheidung.
        </p>
      </div>
    </AppShell>
  )
}
