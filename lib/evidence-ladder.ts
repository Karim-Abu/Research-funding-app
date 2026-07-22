// R6 Evidence-Statusleiter — Coverage ≠ Correctness.
// Der Status wird im Backend abgeleitet (app/review/evidence_status.py) und
// hier NUR gerendert. Kernregel: location_found (Textstelle gefunden) ist
// keine fachliche Verifikation und darf nie grün/„belegt" erscheinen —
// grün ist ausschliesslich supports_strongly.

export type SupportStatus =
  | "not_required"
  | "evidence_missing"
  | "location_found"
  | "supports_partially"
  | "supports_strongly"
  | "conflict_or_uncertain"
  | "human_review_required"

export const SUPPORT_STATUS_LABELS: Record<SupportStatus, string> = {
  not_required: "Kein Beleg erforderlich",
  evidence_missing: "Beleg fehlt",
  location_found: "Textstelle gefunden – fachliche Prüfung offen",
  supports_partially: "Teilweise gestützt",
  supports_strongly: "Stark gestützt",
  conflict_or_uncertain: "Widersprüchlich/unklar",
  human_review_required: "Menschliche Prüfung erforderlich",
}

// Kurzform für enge Stellen (Chips in Listen); gleiche Aussage, weniger Text.
export const SUPPORT_STATUS_SHORT_LABELS: Record<SupportStatus, string> = {
  not_required: "Kein Beleg nötig",
  evidence_missing: "Beleg fehlt",
  location_found: "Textstelle gefunden",
  supports_partially: "Teilweise gestützt",
  supports_strongly: "Stark gestützt",
  conflict_or_uncertain: "Widersprüchlich",
  human_review_required: "Prüfung nötig",
}

// Badge-Styles: grün NUR für supports_strongly; location_found bewusst
// neutral-blau (Fundstelle = Abdeckung, keine Bewertung).
export const SUPPORT_STATUS_STYLES: Record<SupportStatus, string> = {
  not_required: "bg-muted text-muted-foreground",
  evidence_missing: "bg-muted text-muted-foreground",
  location_found: "border border-blue-200 bg-blue-50 text-blue-800",
  supports_partially: "bg-status-partial/12 text-status-partial",
  supports_strongly: "bg-status-fulfilled/12 text-status-fulfilled",
  conflict_or_uncertain: "bg-status-blocker/12 text-status-blocker",
  human_review_required: "bg-status-partial/12 text-status-partial",
}

// RUN 4A — Kurzdefinition je Stufe (aufklappbar unter Beleg-Listen). Reihen-
// folge = fachliche Leiter von «gefunden» bis «widersprüchlich».
export const SUPPORT_LADDER_ORDER: SupportStatus[] = [
  "location_found",
  "supports_partially",
  "supports_strongly",
  "conflict_or_uncertain",
  "human_review_required",
  "evidence_missing",
  "not_required",
]

export const SUPPORT_STATUS_DEFINITIONS: Record<SupportStatus, string> = {
  location_found:
    "Die Passage ist in der Quelle auffindbar; die fachliche Stützung ist noch offen.",
  supports_partially: "Die Passage trägt nur einen Teil der Aussage.",
  supports_strongly: "Die Passage trägt die konkrete Aussage direkt.",
  conflict_or_uncertain:
    "Die Quelle widerspricht der Aussage oder bleibt unklar.",
  human_review_required:
    "Die Stützung braucht eine menschliche Entscheidung — sie wurde noch nicht abschliessend geprüft.",
  evidence_missing: "Für die Aussage ist noch keine Quelle verknüpft.",
  not_required: "Für diesen Punkt ist kein Beleg erforderlich.",
}

// Erläuterung unter Beleg-Listen: was die Stufe aussagt — und was nicht.
export const SUPPORT_LADDER_HINT =
  "«Textstelle gefunden» heisst nur: Der Text ist in der Quelle auffindbar. " +
  "Ob die Aussage fachlich gestützt ist, zeigen die Stufen «Teilweise/Stark " +
  "gestützt» – die abschliessende Bewertung bleibt bei Ihnen."

export function isSupportStatus(value: unknown): value is SupportStatus {
  return typeof value === "string" && value in SUPPORT_STATUS_LABELS
}

// Anzeige-Fallback, wenn ein Anker (Mock-Modus / ältere Antworten) noch kein
// support_status trägt. Identisch zur Backend-Regel ohne Reliability-Urteil
// (derive_anchor_support_status) — bewusst nie eine supports_*-Stufe.
export function supportStatusFromVerification(
  verification: "unverified" | "exact_verified" | "human_verified" | "rejected"
): SupportStatus {
  switch (verification) {
    case "exact_verified":
    case "human_verified":
      return "location_found"
    case "rejected":
      return "conflict_or_uncertain"
    default:
      return "human_review_required"
  }
}
