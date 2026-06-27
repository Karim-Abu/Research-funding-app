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

// Topbar selector: only the active project. Switching projects without a
// real project context would silently keep showing p1 data on every page —
// a demo trap. Multi-project context is post-evaluation work.
export const projects: Project[] = [
  { id: "p1", title: "KI-gestützte Materialentwicklung" },
]

export const activeProjectId = "p1"

// 8 Schritte, die auf 6 Screens abgebildet werden.
// Schritt 2 UND 4 -> "Quellen & Evidenz"; Schritt 6 UND 7 -> "Review".
export const workflowSteps: WorkflowStep[] = [
  { step: 1, label: "Intake", subLabel: "Projekt & Daten", href: "/intake" },
  { step: 2, label: "Quellen", subLabel: "Unterlagen", href: "/quellen" },
  { step: 3, label: "Anforderungen", shortLabel: "Anford.", subLabel: "Fördervoraussetzungen", href: "/anforderungen" },
  { step: 4, label: "Evidenz", subLabel: "Belege", href: "/quellen?tab=evidenz" },
  // Beta: eine Editier-Oberfläche — der Entwurf wird im Review geprüft und
  // bearbeitet; /editor ist aus der Navigation nicht erreichbar.
  { step: 5, label: "Entwurf prüfen", shortLabel: "Entwurf", subLabel: "Antragstext", href: "/review" },
  { step: 6, label: "Review", subLabel: "Qualitätsprüfung", href: "/review" },
  {
    step: 7,
    label: "Abschluss",
    subLabel: "Freigabe",
    href: "/review",
  },
  { step: 8, label: "Export", subLabel: "Abgabe", href: "/export" },
]

// Dashboard project cards — 4 demo entries covering distinct states.
// Realistic, neutral project names — no test/E2E markers.
export const dashboardProjects: DashboardProject[] = [
  {
    id: "dp1",
    title: "KI-gestützte Materialentwicklung",
    profileLabel: "Innosuisse Beta-Profil",
    fundingProgram: "Innosuisse",
    applicationType: "Innovationsprojekt",
    deadline: "Frist: 15. Aug. 2026",
    deadlineIso: "2026-08-15",
    progressPercent: 78,
    currentStep: 5,
    cardStatus: "in_bearbeitung",
    lastEditedLabel: "Zuletzt bearbeitet: heute, 09:42 von Anna Keller",
    nextAction: "continue_draft",
    people: [
      { name: "Anna Keller", initials: "AK" },
      { name: "Tobias Frei", initials: "TF" },
      { name: "Mara Stucki", initials: "MS" },
    ],
  },
  {
    id: "dp2",
    title: "Sensorik-Plattform für Produktionsanlagen",
    profileLabel: "Innosuisse Beta-Profil",
    fundingProgram: "Innosuisse",
    applicationType: "Innovationsprojekt",
    deadline: "Frist: 30. Sep. 2026",
    deadlineIso: "2026-09-30",
    progressPercent: 42,
    currentStep: 4,
    cardStatus: "blockiert",
    lastEditedLabel: "Zuletzt bearbeitet: gestern, 14:15 von Tobias Frei",
    nextAction: "resume_analysis",
    warningBadge: "durchlauf_gestoppt",
    people: [
      { name: "Tobias Frei", initials: "TF" },
      { name: "Luca Bianchi", initials: "LB" },
    ],
  },
  {
    id: "dp3",
    title: "Digitale Zwillinge in der Medizintechnik",
    profileLabel: "Innosuisse Beta-Profil",
    fundingProgram: "Innosuisse",
    applicationType: "Innovationsprojekt",
    deadline: "Frist: 31. Okt. 2026",
    deadlineIso: "2026-10-31",
    progressPercent: 61,
    currentStep: 6,
    cardStatus: "in_bearbeitung",
    lastEditedLabel: "Zuletzt bearbeitet: heute, 08:03 von Anna Keller",
    nextAction: "review_analysis",
    analysisRunning: true,
    people: [
      { name: "Anna Keller", initials: "AK" },
      { name: "Mara Stucki", initials: "MS" },
      { name: "Jonas Meier", initials: "JM" },
      { name: "Luca Bianchi", initials: "LB" },
    ],
  },
  {
    id: "dp4",
    title: "Nachhaltige Kreislaufwirtschaft Verpackungen",
    profileLabel: "Innosuisse Beta-Profil",
    fundingProgram: "Innosuisse",
    applicationType: "Innovationsprojekt",
    deadline: "Frist: 28. Feb. 2027",
    deadlineIso: "2027-02-28",
    progressPercent: 91,
    currentStep: 7,
    cardStatus: "review_offen",
    lastEditedLabel: "Zuletzt bearbeitet: vorgestern, 11:30 von Anna Keller",
    nextAction: "approve_review",
    warningBadge: "freigabe_offen",
    people: [
      { name: "Anna Keller", initials: "AK" },
      { name: "Jonas Meier", initials: "JM" },
      { name: "Mara Stucki", initials: "MS" },
    ],
  },
]
