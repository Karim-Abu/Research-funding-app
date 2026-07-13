// Der EINE Workflow-Katalog (6 Schritte) und die Schrittstatus-Ableitung.
// Stepper, Sidebar und Dashboard lesen Labels/Routen ausschliesslich hier —
// keine zweite Schrittliste im Frontend. Schrittstatus entsteht NUR aus
// Backend-Artefakten (workflow_summary, Runs, kanonischer Review-Status,
// Partner/Budget-Feldern) — ein besuchter Screen ist nie «erledigt».
//
// Hinweis: Das Backend (backend/app/workflow_summary.py) nummeriert weiterhin
// 8 Schritte; die Übersetzung erfolgt explizit in lib/projects.ts
// (BACKEND_STEP_TO_UI_STEP). Dashboard-Karten (latest_run_id) und die
// Run-Auswahl-Ladder (lib/active-run.ts) können bei «neuer Lauf fehlgeschlagen
// nach erfolgreichem Lauf» bewusst unterschiedliche Signale zeigen: die Karte
// warnt vor dem letzten Lauf, die Schritte zeigen den Stand der Artefakte.

import type { ActiveRunSelection } from "./active-run"
import type { PartnerDto } from "./partners"
import type { ProjectDto } from "./projects"
import type { AnalysisRunDto } from "./runs"
import type { ReviewStatusDto } from "./status"

export type WorkflowStepId =
  | "projekt"
  | "partner"
  | "analyse"
  | "entwurf"
  | "pruefung"
  | "uebernahme"

export interface WorkflowStepDef {
  id: WorkflowStepId
  step: 1 | 2 | 3 | 4 | 5 | 6
  /** Der EINE sichtbare Name des Schritts (Stepper, Sidebar, Karten). */
  label: string
  subLabel: string
  /** Kanonisches Sprungziel des Schritts. */
  href: string
  /** Alle Routen (pathnames), die zu diesem Schritt gehören. */
  routes: readonly string[]
}

export const WORKFLOW_STEPS: readonly WorkflowStepDef[] = [
  {
    id: "projekt",
    step: 1,
    label: "Projekt & Unterlagen",
    subLabel: "Projekt anlegen, Antrag importieren, Quellen",
    href: "/quellen",
    routes: ["/intake", "/import", "/quellen"],
  },
  {
    id: "partner",
    step: 2,
    label: "Partner & Budget",
    subLabel: "Konsortium & Budget",
    href: "/partner",
    routes: ["/partner"],
  },
  {
    id: "analyse",
    step: 3,
    label: "Analyse & Recherche",
    subLabel: "Anforderungen & Evidenz",
    href: "/anforderungen",
    routes: ["/anforderungen"],
  },
  {
    id: "entwurf",
    step: 4,
    label: "Antragsentwurf",
    subLabel: "Feldtexte bearbeiten",
    href: "/editor",
    routes: ["/editor"],
  },
  {
    id: "pruefung",
    step: 5,
    label: "Qualitätsprüfung",
    subLabel: "Freigabe & Qualität",
    href: "/review",
    routes: ["/review"],
  },
  {
    id: "uebernahme",
    step: 6,
    label: "Innolink-Übernahme",
    subLabel: "Manuell übernehmen & kopieren",
    href: "/export",
    routes: ["/export", "/portal-transfer"],
  },
]

export type StepUiStatus =
  | "nicht_begonnen"
  | "in_bearbeitung"
  | "eingaben_fehlen"
  | "bereit_zur_pruefung"
  | "abgeschlossen"
  | "blockiert"
  | "fehlgeschlagen"

export const STEP_STATUS_LABELS: Record<StepUiStatus, string> = {
  nicht_begonnen: "Nicht begonnen",
  in_bearbeitung: "In Bearbeitung",
  eingaben_fehlen: "Eingaben fehlen",
  bereit_zur_pruefung: "Bereit zur Prüfung",
  abgeschlossen: "Abgeschlossen",
  blockiert: "Blockiert",
  fehlgeschlagen: "Fehlgeschlagen",
}

/** Neutraler Ausgangszustand (Mock-Modus, Ladefehler): nie fake-«done». */
export const NEUTRAL_STEP_STATUSES: Record<WorkflowStepId, StepUiStatus> = {
  projekt: "nicht_begonnen",
  partner: "nicht_begonnen",
  analyse: "nicht_begonnen",
  entwurf: "nicht_begonnen",
  pruefung: "nicht_begonnen",
  uebernahme: "nicht_begonnen",
}

export function stepForPathname(pathname: string): WorkflowStepDef | null {
  const path = pathname.split("?")[0]
  return (
    WORKFLOW_STEPS.find((s) =>
      s.routes.some((r) => path === r || path.startsWith(`${r}/`))
    ) ?? null
  )
}

export function stepByNumber(step: number): WorkflowStepDef | null {
  return WORKFLOW_STEPS.find((s) => s.step === step) ?? null
}

export interface WorkflowStatusInput {
  project?: ProjectDto | null
  runs?: readonly AnalysisRunDto[] | null
  activeRun?: ActiveRunSelection | null
  reviewStatus?: ReviewStatusDto | null
  /** null = Partnerliste nicht ladbar (unbekannt), [] = keine Partner. */
  partners?: readonly PartnerDto[] | null
}

const ACTIVE_RUN_STATUSES: ReadonlySet<string> = new Set([
  "created",
  "running",
  "paused_for_review",
])

function newestRun(
  runs: readonly AnalysisRunDto[] | null | undefined
): AnalysisRunDto | null {
  if (!runs || runs.length === 0) return null
  return [...runs].sort(
    (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)
  )[0]
}

function hasBudgetCore(project: ProjectDto): boolean {
  return (
    project.direct_total_project_costs_excluding_overhead != null &&
    project.total_requested_funding != null
  )
}

/** Ableitungsmatrix — siehe Plan «Eine konsistente Workflow- und Run-Wahrheit».
 *  S = workflow_summary · latest = neuester Run beliebigen Status (expliziter
 *  created_at-Sort) · A = aktiver abgeschlossener Run (Ladder) · RS =
 *  kanonischer Review-Status von A. */
export function deriveStepStatuses(
  input: WorkflowStatusInput
): Record<WorkflowStepId, StepUiStatus> {
  const project = input.project ?? null
  const summary = project?.workflow_summary ?? null
  const latest = newestRun(input.runs)
  const active = input.activeRun?.run ?? null
  const rs = input.reviewStatus ?? null
  const approved = rs?.approval_status === "approved" && !rs.stale

  const result: Record<WorkflowStepId, StepUiStatus> = {
    ...NEUTRAL_STEP_STATUSES,
  }
  if (!project) return result

  // 1 — Projekt & Unterlagen: Artefakt «verarbeitete Quellen» (Backend-Summary).
  if (summary?.next_action === "upload_sources") {
    result.projekt = "eingaben_fehlen"
  } else if (!summary) {
    result.projekt = "in_bearbeitung"
  } else {
    result.projekt = "abgeschlossen"
  }

  // 2 — Partner & Budget: Partnerliste + Budget-Kernfelder des Projekts.
  if (input.partners == null) {
    // Partnerstand unbekannt (Ladefehler): keine Vollständigkeit behaupten.
    result.partner = hasBudgetCore(project) ? "in_bearbeitung" : "eingaben_fehlen"
  } else if (input.partners.length === 0 || !hasBudgetCore(project)) {
    result.partner = "eingaben_fehlen"
  } else {
    result.partner = "abgeschlossen"
  }

  // 3 — Analyse & Recherche: Run-Lebenszyklus + kanonischer Review-Status.
  if (latest && ACTIVE_RUN_STATUSES.has(latest.status)) {
    result.analyse = "in_bearbeitung"
  } else if (!active) {
    if (latest?.status === "failed") result.analyse = "fehlgeschlagen"
    else if (latest?.status === "stopped") result.analyse = "blockiert"
    else result.analyse = "nicht_begonnen"
  } else if (rs && rs.blocker_count > 0) {
    result.analyse = "blockiert"
  } else if (!rs || rs.stale) {
    result.analyse = "in_bearbeitung"
  } else {
    result.analyse = "abgeschlossen"
  }

  // 4 — Antragsentwurf: Nutzer-Drafts (Backend-Summary) bzw. Freigabe.
  if (!active) {
    result.entwurf = "nicht_begonnen"
  } else if (approved) {
    result.entwurf = "abgeschlossen"
  } else if (summary?.next_action === "continue_draft") {
    result.entwurf = "in_bearbeitung"
  } else {
    result.entwurf = "nicht_begonnen"
  }

  // 5 — Qualitätsprüfung: ohne Review-Status «Noch nicht geprüft», nie eine 0.
  if (!active || !rs) {
    result.pruefung = "nicht_begonnen"
  } else if (approved) {
    result.pruefung = "abgeschlossen"
  } else if (rs.blocker_count > 0 || rs.approval_status === "blocked") {
    result.pruefung = "blockiert"
  } else if (rs.approval_status === "changes_required") {
    result.pruefung = "eingaben_fehlen"
  } else if (rs.stale || rs.approval_status === "stale") {
    result.pruefung = "in_bearbeitung"
  } else {
    result.pruefung = "bereit_zur_pruefung"
  }

  // 6 — Innolink-Übernahme: nie «Abgeschlossen» — es gibt kein Portal-
  // Writeback, die manuelle Übernahme ist für die App nicht verifizierbar.
  if (active && rs && rs.blocker_count > 0) {
    result.uebernahme = "blockiert"
  } else if (active && approved) {
    result.uebernahme = "in_bearbeitung"
  } else {
    result.uebernahme = "nicht_begonnen"
  }

  return result
}
