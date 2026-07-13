// Presentation helpers for the Entwurf / Antragsentwurf (portal field editor).
// Pure functions + label maps. No backend calls, no contract changes.

// ---------------------------------------------------------------------------
// Field status — "Bereit" means the draft is ready to carry forward; it is NOT
// the same as a requirement being "Erfüllt" or evidence being "Verifiziert".
// ---------------------------------------------------------------------------
export type DraftFieldStatus =
  | "ready"
  | "needs_review"
  | "in_progress"
  | "ai_suggestion"
  | "no_draft"
  | "no_evidence"
  | "blocked"
  | "open"

export const DRAFT_STATUS_LABELS: Record<DraftFieldStatus, string> = {
  ready: "Bereit",
  needs_review: "Prüfung nötig",
  in_progress: "In Bearbeitung",
  ai_suggestion: "Vorschlag zur Prüfung",
  no_draft: "Kein Entwurf",
  no_evidence: "Beleg fehlt",
  blocked: "Blockiert",
  open: "Offen",
}

export const DRAFT_STATUS_STYLE: Record<DraftFieldStatus, string> = {
  ready: "bg-status-fulfilled/12 text-status-fulfilled",
  needs_review: "bg-status-partial/12 text-status-partial",
  in_progress: "bg-muted text-foreground",
  // KI-Akzentfarbe wie beim bestehenden "KI-Vorschlag (temporär)"-Chip.
  ai_suggestion: "bg-primary/10 text-primary",
  no_draft: "bg-muted text-muted-foreground",
  no_evidence: "bg-status-partial/12 text-status-partial",
  blocked: "bg-destructive/10 text-destructive",
  open: "bg-muted text-muted-foreground",
}

// ---------------------------------------------------------------------------
// Evidence status (field level) — keeps the evidence wording distinct.
// ---------------------------------------------------------------------------
export type DraftEvidenceStatus = "verified" | "review" | "open"

export const DRAFT_EVIDENCE_LABELS: Record<DraftEvidenceStatus, string> = {
  verified: "Fundstelle bestätigt",
  review: "Prüfung nötig",
  open: "Offen",
}

export const DRAFT_EVIDENCE_STYLE: Record<DraftEvidenceStatus, string> = {
  verified: "bg-status-fulfilled/12 text-status-fulfilled",
  review: "bg-status-partial/12 text-status-partial",
  open: "bg-muted text-muted-foreground",
}

// ---------------------------------------------------------------------------
// Character limit — readable counter with a calm colour cue.
// ---------------------------------------------------------------------------
export type CharLimitState = "none" | "ok" | "near" | "over"

export interface CharLimitInfo {
  state: CharLimitState
  text: string
  className: string
}

function formatNumber(n: number): string {
  return n.toLocaleString("de-CH")
}

export function charLimitInfo(count: number, limit?: number | null): CharLimitInfo {
  if (limit == null) {
    return {
      state: "none",
      text: "Kein Zeichenlimit hinterlegt",
      className: "text-muted-foreground",
    }
  }
  const base = `${formatNumber(count)} / ${formatNumber(limit)} Zeichen`
  if (count > limit) {
    return {
      state: "over",
      text: `${base} · Limit überschritten`,
      className: "text-destructive",
    }
  }
  if (count >= limit * 0.9) {
    return { state: "near", text: base, className: "text-status-partial" }
  }
  return { state: "ok", text: base, className: "text-status-fulfilled" }
}

export const OVER_LIMIT_WARNING =
  "Dieses Feld überschreitet das Innolink-Zeichenlimit. Kürzen Sie den Text vor dem Export."

// ---------------------------------------------------------------------------
// Placeholder / open-input detection. This is deliberately broad for the
// editor's "jump to" UX; export/readiness status uses lib/placeholders.ts.
// ---------------------------------------------------------------------------
function placeholderRegex(): RegExp {
  return /\[\[[^\]]*\]\]|\bTODO\b|\btbd\b|Angabe ergänzen|Platzhalter/gi
}

export function hasPlaceholder(text: string): boolean {
  return placeholderRegex().test(text)
}

export interface PlaceholderMatch {
  start: number
  end: number
}

/** All placeholder ranges, in order — drives the count + "next" cycling UX. */
export function placeholderMatches(text: string): PlaceholderMatch[] {
  const re = placeholderRegex()
  const matches: PlaceholderMatch[] = []
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    matches.push({ start: m.index, end: m.index + m[0].length })
    if (m[0].length === 0) re.lastIndex += 1
  }
  return matches
}

/**
 * Focus the textarea and select a range so the placeholder is visibly marked
 * (not just a cursor jump). The scroll position is estimated from the line
 * count — the one presentation-DOM helper in this module, shared by the shell
 * banner and the review-hint actions.
 */
export function selectTextareaRange(
  node: HTMLTextAreaElement,
  text: string,
  match: PlaceholderMatch
): void {
  node.focus()
  node.setSelectionRange(match.start, match.end)
  const lineBefore = text.slice(0, match.start).split("\n").length
  node.scrollTop = Math.max(0, (lineBefore - 2) * 20)
}

export const PLACEHOLDER_TITLE = "Platzhalter vorhanden"

export function placeholderCountText(count: number): string {
  return count === 1 ? "1 offene Angabe im Text." : `${count} offene Angaben im Text.`
}

// AI actions are not wired to a backend yet — communicate that honestly.
export const AI_ACTION_HINT = "Im Mock-Modus lokal simuliert · echte KI-Überarbeitung folgt später."
export const LIVE_SAVE_HINT = "Speichern ist im Live-Modus noch nicht verfügbar."

// ---------------------------------------------------------------------------
// User-friendly fallbacks — never show raw ids/enums as the main label.
// ---------------------------------------------------------------------------
export const DRAFT_FALLBACK = {
  unnamedField: "Unbenanntes Feld",
  fallbackSection: "Weitere Felder",
  noDraft: "Für dieses Feld liegt noch kein Entwurf vor.",
  noEvidence: "Noch keine Evidenz mit diesem Feld verknüpft.",
  noRequirements: "Noch keine Anforderungen mit diesem Feld verknüpft.",
  noReview: "Noch nicht geprüft.",
  noEditor: "Noch keine Bearbeitung protokolliert.",
} as const
