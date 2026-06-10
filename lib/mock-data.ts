// Dummy-Daten für den Prototyp. Keine echten Daten, keine Backend-Aufrufe.
import type { DashboardProject, Project, User, WorkflowStep } from "./types"

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
  { step: 3, label: "Anforderung", shortLabel: "Anforder.", subLabel: "Fördervoraussetzungen", href: "/anforderungen" },
  { step: 4, label: "Evidenz", subLabel: "Belege", href: "/quellen?tab=evidenz" },
  { step: 5, label: "Entwurf", subLabel: "Antragstext", href: "/editor" },
  { step: 6, label: "Review", subLabel: "Qualitätsprüfung", href: "/review" },
  {
    step: 7,
    label: "Abschluss",
    subLabel: "Freigabe",
    href: "/review?tab=freigabe",
  },
  { step: 8, label: "Export", subLabel: "Abgabe", href: "/export" },
]

// Dashboard project cards — 4 dummy entries covering distinct states.
export const dashboardProjects: DashboardProject[] = [
  {
    id: "dp1",
    title: "KI-gestützte Materialentwicklung (Dummy)",
    profileLabel: "Innosuisse Beta-Profil",
    deadline: "Frist: 15. August 2026 (Dummy)",
    progressPercent: 78,
    currentStep: 5,
    lastEditedLabel: "Zuletzt bearbeitet: heute, 09:42 von Anna Keller",
    nextAction: "continue_draft",
  },
  {
    id: "dp2",
    title: "Sensorik-Plattform für Produktionsanlagen (Dummy)",
    profileLabel: "Innosuisse Beta-Profil",
    deadline: "Frist: 30. September 2026 (Dummy)",
    progressPercent: 42,
    currentStep: 4,
    lastEditedLabel: "Zuletzt bearbeitet: gestern, 14:15 von Tobias Frei",
    nextAction: "resume_analysis",
    warningBadge: "durchlauf_gestoppt",
  },
  {
    id: "dp3",
    title: "Nachhaltige Kreislaufwirtschaft – Verpackungen (Dummy)",
    profileLabel: "Innosuisse Beta-Profil",
    deadline: "Frist: 31. Oktober 2026 (Dummy)",
    progressPercent: 61,
    currentStep: 6,
    lastEditedLabel: "Zuletzt bearbeitet: heute, 08:03 von Anna Keller",
    nextAction: "review_analysis",
    analysisRunning: true,
  },
  {
    id: "dp4",
    title: "Digitale Zwillinge in der Medizintechnik (Dummy)",
    profileLabel: "Innosuisse Beta-Profil",
    deadline: "Frist: 28. Februar 2027 (Dummy)",
    progressPercent: 91,
    currentStep: 7,
    lastEditedLabel: "Zuletzt bearbeitet: vorgestern, 11:30 von Anna Keller",
    nextAction: "approve_review",
    warningBadge: "freigabe_offen",
  },
]
