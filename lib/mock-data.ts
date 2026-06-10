// Dummy-Daten für den Prototyp. Keine echten Daten, keine Backend-Aufrufe.
import type { Project, User, WorkflowStep } from "./types"

export const currentUser: User = {
  name: "Anna Keller",
  displayRole: "Projektleiterin",
  role: "lead_admin",
}

export const memberUser: User = {
  name: "Tobias Frei",
  displayRole: "Projektmitglied",
  role: "member",
}

export const projects: Project[] = [
  { id: "p1", title: "KI-gestützte Materialentwicklung (Dummy)" },
  { id: "p2", title: "Sensorik-Plattform (Dummy)" },
]

export const activeProjectId = "p1"

// 8 Schritte, die auf 6 Screens abgebildet werden.
// Schritt 2 UND 4 -> "Quellen & Evidenz"; Schritt 6 UND 7 -> "Review".
export const workflowSteps: WorkflowStep[] = [
  { step: 1, label: "Intake", subLabel: "Projekt & Daten", href: "/intake" },
  { step: 2, label: "Quellen", subLabel: "Unterlagen", href: "/quellen" },
  {
    step: 3,
    label: "Anforderungen",
    subLabel: "Fördervoraussetzungen",
    href: "/anforderungen",
  },
  { step: 4, label: "Evidenz", subLabel: "Belege", href: "/quellen?tab=evidenz" },
  { step: 5, label: "Entwurf", subLabel: "Antragstext", href: "/editor" },
  { step: 6, label: "Review", subLabel: "Qualitätsprüfung", href: "/review" },
  {
    step: 7,
    label: "Finalisierung",
    subLabel: "Freigabe",
    href: "/review?tab=freigabe",
  },
  { step: 8, label: "Export", subLabel: "Abgabe", href: "/export" },
]
