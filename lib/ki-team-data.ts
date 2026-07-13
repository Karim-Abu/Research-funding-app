// Statischer Rollenkatalog für die Transparenzseite "KI-Team".
// Single Source of Truth für Phasenband, Rollenkarten und Detail-Drawer.
// Bewusst statisch: keine Live-Daten, keine API-Aufrufe, keine Modellnamen.
import { WORKFLOW_STEPS, type WorkflowStepDef } from "./workflow"

// ---------------------------------------------------------------------------
// Modus
// ---------------------------------------------------------------------------

export type RoleMode = "ki" | "regelbasiert" | "hybrid" | "mensch"

export const MODE_LABELS: Record<RoleMode, string> = {
  ki: "KI-gestützt",
  regelbasiert: "Regelbasiert",
  hybrid: "KI + Regeln",
  mensch: "Mensch",
}

// Nutzerfreundliche Status-Chips (keine technischen Backend-Status).
export type RoleStatusTone = "ready" | "active" | "demo" | "development" | "none"

// ---------------------------------------------------------------------------
// Rollen
// ---------------------------------------------------------------------------

export interface KiTeamRole {
  id: string
  name: string
  mode: RoleMode
  /** Kurzbeschreibung auf der Karte. */
  short: string
  /** Aufgabe im Drawer (1–2 Sätze). */
  aufgabe: string
  /** Wann die Rolle aktiv ist. */
  aktiv: string
  /** Eingaben → Ausgaben, nutzerverständlich. */
  eingaben: string
  ausgaben: string
  /** Statische Provider-Angabe — keine echten Modellnamen. */
  provider: string
  /** Welche Daten diese Rolle sieht (Metadaten-Beschreibung, keine Inhalte). */
  daten: string
  /** Menschliche Prüfung: was Nutzer:innen bestätigen. */
  menschlichePruefung: string
  /** Grenzen & Risiken, ehrlich formuliert. */
  grenzen: string
  /** Status-Chip auf der Karte. */
  statusLabel: string
  statusTone: RoleStatusTone
  /** Nur im Details-Modus, eingeklappt unter "Technische Details". */
  technischeQuelle: string
  /** Datenklassen-Regel, nur unter "Technische Details". */
  datenklassenRegel: string
}

export const kiTeamRoles: KiTeamRole[] = [
  {
    id: "ablaufsteuerung",
    name: "Ablaufsteuerung",
    mode: "regelbasiert",
    short: "Ein festes Programm steuert die Schritte der Analyse. Keine KI.",
    aufgabe:
      "Steuert die Reihenfolge der Analyse-Schritte nach einem festen, dokumentierten Ablauf. Es kommt keine KI zum Einsatz.",
    aktiv: "Bei jeder Analyse",
    eingaben: "Projektzustand",
    ausgaben: "Ablauf der Analyse-Schritte",
    provider: "Ohne KI — festes Programm",
    daten: "Nur den Bearbeitungsstand des Projekts — keine Inhalte Ihrer Unterlagen.",
    menschlichePruefung: "Keine — der Ablauf ist fest vorgegeben und für alle Projekte gleich.",
    grenzen: "Bricht bei Fehlern kontrolliert ab und setzt nicht selbst fort.",
    statusLabel: "Bereit",
    statusTone: "ready",
    technischeQuelle: "runs/graph.py, executor",
    datenklassenRegel: "Verarbeitet nur Zustandsdaten, keine Dokumentinhalte.",
  },
  {
    id: "fakten-leser",
    name: "Fakten-Leser (A1)",
    mode: "ki",
    short: "Liest Ihre Unterlagen und schlägt Projekt-Fakten vor.",
    aufgabe:
      "Liest Ihre hochgeladenen Unterlagen und schlägt daraus Projekt-Fakten vor. Alle Vorschläge bleiben unbestätigt, bis Sie sie prüfen.",
    aktiv: "In der Analyse",
    eingaben: "Ihre Quellen",
    ausgaben: "Vorgeschlagene Fakten (unbestätigt)",
    provider: "Kontrollierter KI-Dienst (Demo)",
    daten: "Ihre hochgeladenen Unterlagen und Projektangaben — innerhalb der kontrollierten Verarbeitung.",
    menschlichePruefung: "Ja — Fakten gelten erst nach Ihrer Bestätigung.",
    grenzen: "Kann Textstellen falsch deuten; Vorschläge sind nie automatisch wahr.",
    statusLabel: "Demo-Modus",
    statusTone: "demo",
    technischeQuelle: "agents/fact_extraction",
    datenklassenRegel: "Sieht vertrauliche Projektdaten nur innerhalb der kontrollierten Verarbeitung.",
  },
  {
    id: "beleg-zuordner",
    name: "Beleg-Zuordner (A1)",
    mode: "hybrid",
    short: "Verknüpft Aussagen mit Fundstellen in Ihren Quellen.",
    aufgabe:
      "Verknüpft Aussagen mit konkreten Fundstellen in Ihren Quellen und zeigt das passende Zitat dazu.",
    aktiv: "In Analyse und Evidenz",
    eingaben: "Aussagen und Quellen",
    ausgaben: "Fundstellen mit Zitat",
    provider: "Kontrollierter KI-Dienst (Demo)",
    daten: "Ihre Quellen und die zu belegenden Aussagen — innerhalb der kontrollierten Verarbeitung.",
    menschlichePruefung: "Ja — «Textstelle gefunden» heisst nicht «fachlich geprüft».",
    grenzen: "Eine Fundstelle ist nicht automatisch ein inhaltlicher Beweis.",
    statusLabel: "Demo-Modus",
    statusTone: "demo",
    technischeQuelle: "agents/evidence_mapping, reliability",
    datenklassenRegel: "Sieht vertrauliche Projektdaten nur innerhalb der kontrollierten Verarbeitung.",
  },
  {
    id: "text-vorschlager",
    name: "Text-Vorschlager (A2)",
    mode: "ki",
    short: "Erstellt auf Wunsch Entwürfe für einzelne Antragsfelder.",
    aufgabe:
      "Erstellt auf Ihren Klick hin Textentwürfe für einzelne Antragsfelder — auf Basis des Feldkontexts und Ihrer bestätigten Belege.",
    aktiv: "Auf Klick im Entwurf",
    eingaben: "Feldkontext und bestätigte Belege",
    ausgaben: "Textvorschlag",
    provider: "Kontrollierter KI-Dienst (Demo)",
    daten: "Den Kontext des jeweiligen Antragsfelds und Ihre bestätigten Belege.",
    menschlichePruefung: "Ja — kein Vorschlag wird automatisch übernommen.",
    grenzen: "Klingt überzeugend, kann trotzdem unbelegt sein — darum Beleganzeige je Aussage.",
    statusLabel: "Demo-Modus",
    statusTone: "demo",
    technischeQuelle: "agents/field_drafting",
    datenklassenRegel: "Kann je nach gewählter Datenklasse blockiert sein.",
  },
  {
    id: "regel-budgetpruefer",
    name: "Regel- & Budgetprüfer",
    mode: "regelbasiert",
    short: "Prüft Pflichtangaben, Zeichenlimits, Partner- und Budgetregeln — immer gleich, nach dokumentierten Regeln.",
    aufgabe:
      "Prüft Pflichtangaben, Zeichenlimits sowie Partner- und Budgetregeln — immer gleich und nach dokumentierten Regeln.",
    aktiv: "Laufend und bei jeder Analyse",
    eingaben: "Projektdaten",
    ausgaben: "Blocker und Hinweise mit Regelquelle",
    provider: "Ohne KI — feste Regeln",
    daten: "Ihre Projektangaben, Partner- und Budgetdaten — nur zur Regelprüfung.",
    menschlichePruefung: "Ja — bei fehlenden Angaben verlangt er Ihre Prüfung, statt zu raten.",
    grenzen: "Prüft Form und Regeln, nicht die fachliche Überzeugungskraft.",
    statusLabel: "Aktiv",
    statusTone: "active",
    technischeQuelle: "rules/, review/checks",
    datenklassenRegel: "Regelprüfung läuft vollständig innerhalb der kontrollierten Verarbeitung.",
  },
  {
    id: "zuverlaessigkeits-pruefer",
    name: "Zuverlässigkeits-Prüfer",
    mode: "regelbasiert",
    short: "Markiert Aussagen ohne ausreichenden Beleg.",
    aufgabe:
      "Gleicht Entwürfe mit den vorhandenen Belegen ab und markiert Aussagen, die noch nicht ausreichend belegt sind.",
    aktiv: "In der Qualitätsprüfung",
    eingaben: "Entwürfe und Belege",
    ausgaben: "Qualitäts-Findings",
    provider: "Ohne KI — feste Regeln",
    daten: "Ihre Entwurfstexte und Belege — nur zum Abgleich, ohne inhaltliche Bewertung.",
    menschlichePruefung: "Ja — Einstufungen sind Hinweise, keine Urteile.",
    grenzen: "Wortbasiert, keine inhaltliche Sinnprüfung; kann Fehlalarme erzeugen.",
    statusLabel: "Aktiv",
    statusTone: "active",
    technischeQuelle: "reliability/gate, sufficiency",
    datenklassenRegel: "Abgleich läuft vollständig innerhalb der kontrollierten Verarbeitung.",
  },
  {
    id: "recherche-schutz",
    name: "Recherche-Schutz (Firewall)",
    mode: "regelbasiert",
    short: "Sorgt dafür, dass keine vertraulichen Details in Web-Suchanfragen gelangen.",
    aufgabe:
      "Prüft jede geplante Web-Suchanfrage und entfernt vertrauliche Details, bevor Sie die Anfrage sehen und freigeben.",
    aktiv: "Vor jeder Websuche",
    eingaben: "Suchanfrage",
    ausgaben: "Geprüfte, bereinigte Anfrage",
    provider: "Ohne KI — feste Regeln",
    daten: "Nur den Text der geplanten Suchanfrage — keine Projektunterlagen.",
    menschlichePruefung: "Ja — Sie geben jede Anfrage frei.",
    grenzen: "Blockiert lieber zu viel als zu wenig.",
    statusLabel: "Aktiv",
    statusTone: "active",
    technischeQuelle: "security/search_query_firewall",
    datenklassenRegel: "Verhindert, dass vertrauliche Inhalte die kontrollierte Verarbeitung verlassen.",
  },
  {
    id: "markt-recherche",
    name: "Markt-Recherche-Hilfe",
    mode: "hybrid",
    short: "Schlägt anonymisierte Suchanfragen vor und ordnet öffentliche Quellen.",
    aufgabe:
      "Schlägt anonymisierte Suchanfragen vor und ordnet gefundene öffentliche Quellen den passenden Marktfragen zu.",
    aktiv: "Bei Quellen/Markt, nach Ihrer Freigabe",
    eingaben: "Abstrahierte Anfragen",
    ausgaben: "Öffentliche Quellen, Marktangaben mit Fundstelle",
    provider: "Kontrollierter KI-Dienst (Demo)",
    daten: "Nur anonymisierte Suchanfragen und öffentliche Quellen — nie Ihre Rohidee.",
    menschlichePruefung: "Ja — jede Anfrage und jede Übernahme.",
    grenzen: "In Entwicklung; im Demo-Modus werden Beispielquellen gezeigt.",
    statusLabel: "In Entwicklung",
    statusTone: "development",
    technischeQuelle: "market/, R8",
    datenklassenRegel: "Erhält keine vertraulichen Projektdetails — nur freigegebene, abstrahierte Anfragen.",
  },
  {
    id: "pruef-zusammenfasser",
    name: "Prüf-Zusammenfasser (A3)",
    mode: "regelbasiert",
    short: "Fasst alle Prüfergebnisse zu einem Gesamtstatus zusammen.",
    aufgabe:
      "Sammelt am Ende jeder Analyse alle Prüfergebnisse ein und fasst sie zu einem Gesamtstatus mit Ihren offenen Prüfpunkten zusammen.",
    aktiv: "Am Ende jeder Analyse",
    eingaben: "Alle Findings",
    ausgaben: "Prüfpaket, Fix Queue",
    provider: "Ohne KI — feste Regeln",
    daten: "Nur die Prüfergebnisse der anderen Rollen — keine Rohinhalte.",
    menschlichePruefung: "Keine automatische Freigabe — die Ergebnisse führen zu Ihren Prüfpunkten.",
    grenzen: "Fasst zusammen, bewertet keine inhaltliche Qualität.",
    statusLabel: "Aktiv",
    statusTone: "active",
    technischeQuelle: "a3_review (deterministisch)",
    datenklassenRegel: "Verarbeitet nur Prüfergebnisse, keine Dokumentinhalte.",
  },
  {
    id: "sie",
    name: "Sie (menschliche Prüfung)",
    mode: "mensch",
    short: "Sie bestätigen Fakten, Belege, Budgetfragen und jeden Text.",
    aufgabe:
      "Sie bestätigen Fakten, Belege, Budgetfragen und jeden Text. Ohne Ihre Freigaben bleibt der Antrag ein Entwurf.",
    aktiv: "An allen Kontrollpunkten",
    eingaben: "Vorschläge",
    ausgaben: "Entscheidungen",
    provider: "—",
    daten: "Sie sehen alles — die volle Übersicht über Ihr Projekt.",
    menschlichePruefung: "Sie sind die menschliche Prüfung — die letzte Instanz für alle Inhalte.",
    grenzen: "Ohne Ihre Freigaben bleibt der Antrag ein Entwurf.",
    statusLabel: "",
    statusTone: "none",
    technischeQuelle: "HITL-Gates",
    datenklassenRegel: "Volle Sicht — Freigaben erfolgen ausschliesslich durch Sie.",
  },
]

// ---------------------------------------------------------------------------
// Phasenzuordnung — referenziert die echten Workflow-Schritte (kein zweites
// Prozessmodell). step entspricht WORKFLOW_STEPS[].step aus lib/workflow.ts
// (6-Schritte-Modell). Rollen dürfen in mehreren Phasen erscheinen.
// ---------------------------------------------------------------------------

export interface PhaseAssignment {
  step: number
  roleIds: string[]
}

export const phaseAssignments: PhaseAssignment[] = [
  // Projekt & Unterlagen: Intake/Quellen inkl. geschützter Webrecherche.
  { step: 1, roleIds: ["ablaufsteuerung", "recherche-schutz", "markt-recherche", "sie"] },
  { step: 2, roleIds: ["regel-budgetpruefer", "sie"] },
  // Analyse & Recherche: Anforderungen + Evidenz (Fakten, Belege).
  { step: 3, roleIds: ["fakten-leser", "regel-budgetpruefer", "beleg-zuordner", "sie"] },
  { step: 4, roleIds: ["text-vorschlager", "sie"] },
  { step: 5, roleIds: ["zuverlaessigkeits-pruefer", "pruef-zusammenfasser", "sie"] },
  { step: 6, roleIds: ["regel-budgetpruefer", "sie"] },
]

export interface KiTeamPhase {
  step: WorkflowStepDef
  roles: KiTeamRole[]
  /** Ob Nutzer:innen in dieser Phase prüfen (Mensch-Marker). */
  hatMenschlichePruefung: boolean
}

const rolesById = new Map(kiTeamRoles.map((r) => [r.id, r]))

export function getKiTeamPhases(): KiTeamPhase[] {
  return phaseAssignments.map((assignment) => {
    const step = WORKFLOW_STEPS.find((s) => s.step === assignment.step)
    if (!step) {
      throw new Error(`Unbekannter Workflow-Schritt: ${assignment.step}`)
    }
    const roles = assignment.roleIds.map((id) => {
      const role = rolesById.get(id)
      if (!role) {
        throw new Error(`Unbekannte Rolle im Phasenkatalog: ${id}`)
      }
      return role
    })
    return {
      step,
      roles,
      hatMenschlichePruefung: roles.some((r) => r.mode === "mensch"),
    }
  })
}

// ---------------------------------------------------------------------------
// Statische Seitentexte
// ---------------------------------------------------------------------------

export const kiTeamTexts = {
  titel: "KI-Team",
  untertitel: "Wer hier arbeitet, was automatisch läuft — und wo Sie entscheiden.",
  intro:
    "Die App kombiniert KI-Vorschläge mit festen Prüfregeln. Sie sehen, welche Rolle wo unterstützt und welche Punkte Sie selbst freigeben.",
  ablaufsteuerungHinweis:
    "Ablaufsteuerung: Ein festes Programm steuert die Reihenfolge der Schritte — keine KI.",
  legende: [
    { mode: "ki" as RoleMode, symbol: "◆", text: "KI-gestützt" },
    {
      mode: "regelbasiert" as RoleMode,
      symbol: "■",
      text: "regelbasiert — läuft immer gleich und nachvollziehbar",
    },
    { mode: "mensch" as RoleMode, symbol: "●", text: "Hier prüfen Sie" },
  ],
  nieEntscheidet: {
    titel: "Was die KI hier nie entscheidet",
    punkte: [
      "Förderfähigkeit und Partnerwahl",
      "Budgetfreigaben",
      "fachliche Richtigkeit von Belegen",
      "finaler Antragstext",
      "Einreichung",
      "Förderwahrscheinlichkeit",
    ],
    schlusssatz:
      "Die App reicht keinen Antrag ein und macht keine Aussage zur Förderwahrscheinlichkeit.",
  },
  woSiePruefen: {
    titel: "Wo Sie prüfen",
    punkte: [
      { phase: "Intake", text: "Datenklasse wählen" },
      { phase: "Quellen", text: "Webrecherche-Anfragen freigeben" },
      { phase: "Evidenz", text: "Belege fachlich bestätigen" },
      { phase: "Entwurf", text: "KI-Vorschläge übernehmen oder verwerfen" },
      { phase: "Prüfung", text: "Blocker und menschliche Prüfpunkte abarbeiten" },
      { phase: "Export", text: "Kopieren bestätigen" },
    ],
  },
  datenSchutz: {
    titel: "Daten & Schutz",
    regeln: [
      "Keine automatische Einreichung",
      "Keine Websuche mit Rohidee",
      "Keine Prompts/Rohdaten im UI",
      "Mensch prüft kritische Punkte",
    ],
  },
  letzterLauf: "Noch kein Lauf",
} as const
