"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import {
  applySegments,
  countChanges,
  diffSuggestion,
  summarizeDiff,
} from "@/lib/diff"
import { rationaleChips } from "@/lib/suggestion-view"
import { VERIFICATION_LABELS, type VerificationStatus } from "@/lib/evidence"
import { charCount } from "@/lib/fields"
import { staleReasonLabel, type A2Suggestion } from "@/lib/redraft"
import { GENERATION_KIND_BADGE_CLASS, generationLabel } from "@/lib/generation-kind"

const WARNING_LABELS: Record<string, string> = {
  contains_placeholders:
    "Der Vorschlag enthält Platzhalter für fehlende Angaben — bitte vor der Übernahme prüfen.",
  based_on_unconfirmed_facts:
    "Der Vorschlag stützt sich teilweise auf noch nicht bestätigte (vorgeschlagene) Fakten.",
  application_language_needs_review:
    "Die Antragssprache wurde aus dem vorhandenen Text abgeleitet. Bitte vor der Übernahme prüfen.",
  // RUN 4B §4 — der Fake-Provider markiert jeden Vorschlag mit diesem Code.
  fake_demo_no_model:
    "Demo-Vorschlag ohne echtes KI-Modell — deterministischer Beispieltext, kein fachlicher Inhalt.",
}

// C3 — konkrete, optionale Ablehnungsgründe (plus Freitext).
const DISMISS_REASONS = [
  "Nicht passend",
  "Fachlich unzutreffend",
  "Eigene Formulierung bevorzugt",
] as const

export interface SuggestionReviewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentText: string
  suggestion: A2Suggestion
  onAccept: () => void
  /** C3 — Teilübernahme: gemergter Abschnittstext aus den gewählten Änderungen. */
  onAcceptPartial?: (mergedText: string) => void
  /** C3 — eigene Bearbeitung öffnen (Sheet schliessen, Editor fokussieren). */
  onEdit?: () => void
  /** C3/C4 — Ablehnen mit optionalem Grund (wird serverseitig persistiert). */
  onDismiss: (reason?: string) => void
  /** RUN 4B §7 — «Neuen Vorschlag erzeugen» (Regenerate über den bestehenden
   *  Redraft-Pfad; der Vorschlag wird nie automatisch übernommen). */
  onRegenerate?: () => void
  accepting?: boolean
}

/**
 * Fullscreen-Side-by-Side-Prüfung eines beratenden A2-Vorschlags mit echtem
 * Satz-Diff (beibehalten/entfernt/neu/umformuliert). Schliessen (X/ESC) lässt
 * den Vorschlag bestehen; «Vorschlag ablehnen» ist die ausdrückliche,
 * persistierte Entscheidung. Kein Provider/Modell ausserhalb der Technischen
 * Details; nichts wird automatisch übernommen.
 */
export function SuggestionReviewDialog({
  open,
  onOpenChange,
  currentText,
  suggestion,
  onAccept,
  onAcceptPartial,
  onEdit,
  onDismiss,
  onRegenerate,
  accepting = false,
}: SuggestionReviewDialogProps) {
  const overLimit = suggestion.character_count > suggestion.character_limit
  const label = generationLabel(suggestion.generation_kind)
  const section = suggestion.section_result
  const chips = rationaleChips(suggestion)
  // 2026-07-24 — die Chip-Wand ist in zwei einklappbare Gruppen aufgeteilt:
  // Änderungs-Begründungen (entfernt/neu) und offen gelassene Fragen.
  const changeChips = chips.filter((chip) => chip.tone !== "offen")
  const openChips = chips.filter((chip) => chip.tone === "offen")
  const wholeOnly = suggestion.accept_mode === "whole_suggestion_only"
  // RUN 4B §5/§6 — eine Quelle für «Fehlende Angaben» (Manifest-Vorschläge
  // tragen sie top-level, Legacy im section_result) und ehrliche Belegzahl:
  // auf dem Read-Pfad gespeicherter Vorschläge ist evidence[] leer, die Zahl
  // steckt dann in den verwendeten Anker-IDs des Proposals.
  const missingInputs =
    suggestion.missing_inputs ?? section?.missing_inputs ?? []
  const evidenceCount =
    suggestion.evidence.length > 0
      ? suggestion.evidence.length
      : (suggestion.proposal?.used_anchor_ids?.length ?? 0)

  const segments = React.useMemo(
    () => diffSuggestion(currentText, suggestion.suggested_text),
    [currentText, suggestion.suggested_text]
  )
  const changeCount = countChanges(segments)

  const [selected, setSelected] = React.useState<ReadonlySet<number>>(new Set())
  const [reasonOpen, setReasonOpen] = React.useState(false)
  const [reasonChoice, setReasonChoice] = React.useState<string | null>(null)
  const [reasonText, setReasonText] = React.useState("")
  // RUN 4B §10 — beim Öffnen landet der Fokus deterministisch auf dem Titel
  // (nicht auf dem ersten interaktiven Element mitten im Diff).
  const titleRef = React.useRef<HTMLHeadingElement | null>(null)
  React.useEffect(() => {
    if (!open) return
    const frame = requestAnimationFrame(() => titleRef.current?.focus())
    return () => cancelAnimationFrame(frame)
  }, [open, suggestion.suggestion_id])

  // v2 (2026-07-24, Opt-out): ALLE Änderungen sind vorausgewählt — der
  // Standardfluss «alles übernehmen» bleibt EIN Klick, abgewählt wird nur,
  // was man nicht will. Nichts passiert ohne den Übernehmen-Klick (HITL).
  const allChangeIndices = React.useMemo(
    () =>
      segments
        .map((segment, index) => ({ segment, index }))
        .filter(({ segment }) => segment.kind !== "beibehalten")
        .map(({ index }) => index),
    [segments]
  )

  // Auswahl/Ablehnungsformular je Vorschlag zurücksetzen.
  React.useEffect(() => {
    setSelected(new Set(allChangeIndices))
    setReasonOpen(false)
    setReasonChoice(null)
    setReasonText("")
  }, [suggestion.suggestion_id, allChangeIndices])

  function confirmDismiss() {
    const reason = [reasonChoice, reasonText.trim()].filter(Boolean).join(" — ")
    onDismiss(reason || undefined)
  }

  // v2-Accept-Weiche: Sind ALLE Änderungen ausgewählt, läuft die exakte
  // Komplett-Übernahme (byte-gleich → ehrliche Herkunft «agent»); der Merge
  // (applySegments) ist nachweislich nicht byte-identisch und bleibt dem
  // Teil-Fall vorbehalten (Herkunft «user»).
  function handleAccept() {
    if (wholeOnly || !onAcceptPartial || selected.size === changeCount) {
      onAccept()
      return
    }
    if (selected.size === 0) return
    onAcceptPartial(applySegments(currentText, segments, selected))
  }

  // 2026-07-24 — Sammel-Auswahl je Änderungsart (reine Auswahl-Logik;
  // applySegments bleibt unverändert).
  const groupIndices = React.useMemo(() => {
    const removed: number[] = []
    const added: number[] = []
    const rephrased: number[] = []
    segments.forEach((segment, index) => {
      if (segment.kind === "entfernt") removed.push(index)
      else if (segment.kind === "hinzugefuegt") added.push(index)
      else if (segment.kind === "umformuliert") rephrased.push(index)
    })
    return { removed, added, rephrased }
  }, [segments])

  function toggleGroup(indices: number[]) {
    setSelected((previous) => {
      const next = new Set(previous)
      const allSelected = indices.every((index) => next.has(index))
      for (const index of indices) {
        if (allSelected) next.delete(index)
        else next.add(index)
      }
      return next
    })
  }

  // v3 (2026-07-24) — Block-Paarung wie im klassischen Diff: konsekutive
  // Änderungssegmente bilden EINEN Änderungsblock (alter Text links, neuer
  // rechts daneben); unveränderte Sätze sind Kontextzeilen in voller Breite.
  type DiffRow =
    | { type: "context"; index: number }
    | { type: "change"; indices: number[] }
  const diffRows = React.useMemo<DiffRow[]>(() => {
    const rows: DiffRow[] = []
    let hunk: number[] = []
    segments.forEach((segment, index) => {
      if (segment.kind === "beibehalten") {
        if (hunk.length > 0) {
          rows.push({ type: "change", indices: hunk })
          hunk = []
        }
        rows.push({ type: "context", index })
      } else {
        hunk.push(index)
      }
    })
    if (hunk.length > 0) rows.push({ type: "change", indices: hunk })
    return rows
  }, [segments])

  function hunkSummary(indices: number[]): string {
    const removed = indices.filter((i) => segments[i].kind === "entfernt").length
    const added = indices.filter(
      (i) => segments[i].kind === "hinzugefuegt"
    ).length
    const rephrased = indices.filter(
      (i) => segments[i].kind === "umformuliert"
    ).length
    const parts: string[] = []
    if (removed > 0)
      parts.push(removed === 1 ? "1 Streichung" : `${removed} Streichungen`)
    if (added > 0)
      parts.push(added === 1 ? "1 neuer Satz" : `${added} neue Sätze`)
    if (rephrased > 0)
      parts.push(
        rephrased === 1 ? "1 Umformulierung" : `${rephrased} Umformulierungen`
      )
    return parts.join(" · ")
  }

  function hunkAriaLabel(indices: number[]): string {
    if (indices.length === 1) {
      const segment = segments[indices[0]]
      return segment.kind === "entfernt"
        ? `Streichung übernehmen: ${segment.before ?? ""}`
        : `Änderung übernehmen: ${segment.after ?? ""}`
    }
    return `Änderungsblock übernehmen: ${hunkSummary(indices)}`
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        data-testid="suggestion-review-sheet"
        className="flex flex-col gap-0 overflow-hidden p-0 data-[side=right]:w-full data-[side=right]:sm:w-[85vw] data-[side=right]:sm:max-w-[85vw]"
      >
        <SheetHeader className="shrink-0 border-b border-border px-6 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <SheetTitle
              ref={titleRef}
              tabIndex={-1}
              className="rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {label} prüfen
            </SheetTitle>
            {suggestion.generation_kind && (
              <span
                className={cn(
                  "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
                  GENERATION_KIND_BADGE_CLASS[suggestion.generation_kind]
                )}
              >
                {suggestion.generation_kind === "model_generated"
                  ? "Live-KI"
                  : suggestion.generation_kind === "fake_demo"
                    ? "Demo"
                    : "Regelbasierte Vorlage"}
              </span>
            )}
          </div>
          <SheetDescription>
            Der Vorschlag folgt der Antragssprache. Nichts wird automatisch
            übernommen — {wholeOnly
              ? "dieser versionierte Vorschlag wird vollständig übernommen oder verworfen."
              : "Sie entscheiden je Änderung."}
          </SheetDescription>
        </SheetHeader>

        <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto px-6 py-4">
          {/* RUN 4B §3 — Screenreader-Zusammenfassung der Änderungen; das
              visuelle Pendant ist die Markierung im Diff selbst. */}
          <p className="sr-only" aria-live="polite" data-testid="diff-sr-summary">
            {summarizeDiff(segments)}
          </p>
          {/* 2026-07-24 — ruhige Zusammenfassung statt Chip-Wand: die eine
              wichtige Zeile steht in der Summary, Details ein Klick dahinter. */}
          {(section || changeChips.length > 0) && (
            <details className="rounded-md border border-border px-3 py-2">
              <summary className="cursor-pointer text-xs font-medium text-foreground">
                Was der Vorschlag ändert — {summarizeDiff(segments)}
              </summary>
              <div className="mt-2 flex flex-col gap-2">
                {/* Fachliche Kurzbilanz: was blieb, was fiel weg, was fehlt,
                    welche Quellen — plus Textumfang alt → neu. Fallbacks:
                    fehlende Section-Liste = 0, nie ein Renderfehler. */}
                {section && (
                  <div
                    className="flex flex-wrap gap-1.5"
                    data-testid="suggestion-summary"
                  >
                    {[
                      `Erhaltene Fakten: ${section.preserved_facts?.length ?? 0}`,
                      `Entfernte/umformulierte Aussagen: ${section.removed_or_reframed_claims?.length ?? 0}`,
                      `Neu eingeführte Aussagen: ${section.new_claims?.length ?? 0}`,
                      `Fehlende Angaben: ${section.missing_inputs?.length ?? 0}`,
                      `Verwendete Belege: ${suggestion.evidence.length}`,
                      `Research-Quellen: ${suggestion.research_sources?.length ?? 0}`,
                      `Zeichen: ${charCount(currentText)} → ${charCount(suggestion.suggested_text)}`,
                    ].map((item) => (
                      <span
                        key={item}
                        className="inline-flex items-center rounded-full border border-border bg-muted/50 px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
                      >
                        {item}
                      </span>
                    ))}
                  </div>
                )}
                {/* C5 — konkrete Begründung statt Pauschalsatz. */}
                {changeChips.length > 0 && (
                  <div
                    className="flex flex-wrap gap-1.5"
                    data-testid="rationale-chips"
                  >
                    {changeChips.map((chip) => (
                      <span
                        key={chip.text}
                        className={cn(
                          "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
                          chip.tone === "entfernt" &&
                            "border-status-partial/40 bg-status-partial/10 text-status-partial",
                          chip.tone === "neu" &&
                            "border-primary/30 bg-primary/10 text-primary"
                        )}
                      >
                        {chip.text}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </details>
          )}
          {openChips.length > 0 && (
            <details
              className="rounded-md border border-border px-3 py-2"
              data-testid="open-questions"
            >
              <summary className="cursor-pointer text-xs font-medium text-foreground">
                Offen gelassene Fragen ({openChips.length})
              </summary>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {openChips.map((chip) => (
                  <span
                    key={chip.text}
                    className="inline-flex items-center rounded-full border border-border bg-muted/50 px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
                  >
                    {chip.text}
                  </span>
                ))}
              </div>
            </details>
          )}

          {/* 2026-07-24 — Sammel-Auswahl je Änderungsart statt 38 Einzelklicks. */}
          {!wholeOnly && onAcceptPartial && changeCount > 0 && (
            <div
              className="flex flex-wrap items-center gap-1.5"
              data-testid="batch-selection"
            >
              <span className="text-xs text-muted-foreground">Sammel-Auswahl:</span>
              {groupIndices.removed.length > 0 && (
                <Button
                  type="button"
                  size="xs"
                  variant="outline"
                  aria-pressed={groupIndices.removed.every((i) => selected.has(i))}
                  onClick={() => toggleGroup(groupIndices.removed)}
                >
                  Alle Streichungen ({groupIndices.removed.length})
                </Button>
              )}
              {groupIndices.added.length > 0 && (
                <Button
                  type="button"
                  size="xs"
                  variant="outline"
                  aria-pressed={groupIndices.added.every((i) => selected.has(i))}
                  onClick={() => toggleGroup(groupIndices.added)}
                >
                  Alle neuen Sätze ({groupIndices.added.length})
                </Button>
              )}
              {groupIndices.rephrased.length > 0 && (
                <Button
                  type="button"
                  size="xs"
                  variant="outline"
                  aria-pressed={groupIndices.rephrased.every((i) => selected.has(i))}
                  onClick={() => toggleGroup(groupIndices.rephrased)}
                >
                  Alle Umformulierungen ({groupIndices.rephrased.length})
                </Button>
              )}
            </div>
          )}

          {/* v3 (2026-07-24) — Block-Paarung wie im klassischen Diff:
              zusammenhängende Änderungen bilden EINEN Block (alter Text links,
              neuer Text direkt daneben, EINE Checkbox pro Block); unveränderte
              Sätze stehen einmal in voller Breite. Kein Volltext-Duplikat. */}
          <div className="min-w-0 overflow-hidden rounded-md border border-border">
            <div className="grid grid-cols-1 gap-x-4 border-b border-border bg-muted/30 px-3 py-1.5 md:grid-cols-2">
              <p
                data-testid="current-text"
                className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
              >
                Aktueller Text
              </p>
              <p
                data-testid="suggestion-text"
                className="text-xs font-semibold uppercase tracking-wide text-primary"
              >
                {label}
              </p>
            </div>
            <div className="flex flex-col px-3 py-2" data-testid="suggestion-diff">
              {segments.length === 0 && (
                <p className="text-sm text-muted-foreground">(leer)</p>
              )}
              {diffRows.map((row) =>
                row.type === "context" ? (
                  <p
                    key={`ctx-${row.index}`}
                    className="whitespace-pre-wrap py-0.5 text-sm leading-relaxed text-muted-foreground"
                  >
                    {segments[row.index].after ?? segments[row.index].before}
                  </p>
                ) : (
                  <div
                    key={`hunk-${row.indices[0]}`}
                    data-diff-hunk={row.indices[0]}
                    className="my-1 grid grid-cols-1 gap-x-4 gap-y-1.5 rounded-md border border-border/70 bg-muted/10 px-2.5 py-2 md:grid-cols-2"
                  >
                    <div className="flex min-w-0 flex-col gap-1">
                      {row.indices.every((i) => segments[i].before === null) ? (
                        <p className="text-xs italic text-muted-foreground">
                          — kein bisheriger Text an dieser Stelle —
                        </p>
                      ) : (
                        row.indices.map((i) =>
                          segments[i].before === null ? null : (
                            <p
                              key={`b-${i}`}
                              className={cn(
                                "whitespace-pre-wrap text-sm leading-relaxed",
                                segments[i].kind === "entfernt" &&
                                  "text-destructive line-through decoration-destructive/60"
                              )}
                            >
                              {segments[i].kind === "umformuliert" &&
                              segments[i].words
                                ? segments[i].words
                                    .filter((w) => w.kind !== "hinzugefuegt")
                                    .map((w, wi) => (
                                      <span
                                        key={wi}
                                        className={cn(
                                          w.kind === "entfernt" &&
                                            "bg-destructive/10 text-destructive line-through"
                                        )}
                                      >
                                        {w.text}{" "}
                                      </span>
                                    ))
                                : segments[i].before}
                            </p>
                          )
                        )
                      )}
                    </div>
                    <div className="flex min-w-0 flex-col gap-1">
                      <div className="flex w-fit items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
                        {!wholeOnly && onAcceptPartial && (
                          <input
                            type="checkbox"
                            checked={row.indices.every((i) => selected.has(i))}
                            onChange={() => toggleGroup(row.indices)}
                            aria-label={hunkAriaLabel(row.indices)}
                          />
                        )}
                        <span>{hunkSummary(row.indices)}</span>
                      </div>
                      {row.indices.map((i) =>
                        segments[i].after === null ? null : (
                          <p
                            key={`a-${i}`}
                            className="whitespace-pre-wrap text-sm leading-relaxed"
                          >
                            {segments[i].kind === "umformuliert" &&
                            segments[i].words
                              ? segments[i].words
                                  .filter((w) => w.kind !== "entfernt")
                                  .map((w, wi) => (
                                    <span
                                      key={wi}
                                      className={cn(
                                        w.kind === "hinzugefuegt" &&
                                          "rounded bg-status-fulfilled/15 font-medium"
                                      )}
                                    >
                                      {w.text}{" "}
                                    </span>
                                  ))
                              : segments[i].after}
                          </p>
                        )
                      )}
                    </div>
                  </div>
                )
              )}
            </div>
          </div>

          <p className="text-xs text-muted-foreground" data-testid="character-count">
            {suggestion.character_count} / {suggestion.character_limit} Zeichen
            {overLimit ? " — über dem Limit" : ""}
          </p>

          {/* RUN 4B §4 — veralteter Vorschlag: Klartext-Grund + nächste Aktion,
              prominent (die Übernahme ist unten deaktiviert). */}
          {suggestion.stale_reason && (
            <p
              role="status"
              data-testid="suggestion-stale-notice"
              className="rounded-md border border-status-partial/40 bg-status-partial/10 px-3 py-2 text-xs text-foreground"
            >
              Vorschlag veraltet: {staleReasonLabel(suggestion.stale_reason)}{" "}
              Erzeugen Sie einen neuen Vorschlag.
            </p>
          )}

          {suggestion.warnings.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2">
              <ul className="flex flex-col gap-1">
                {suggestion.warnings.map((w) => (
                  <li
                    key={w}
                    role="status"
                    data-testid={`warning-${w}`}
                    className="text-xs text-amber-900"
                  >
                    {WARNING_LABELS[w] ?? w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* RUN 4B §5 — «Fehlende Angaben» als primäre Sektion: Titel, warum,
              betroffener Innolink-Punkt und nächste Aktion — nie Requirement-
              IDs. (Ein Schweregrad ist im Vertrag nicht vorhanden.) */}
          {missingInputs.length > 0 && (
            <section
              className="flex flex-col gap-1.5 rounded-md border border-status-partial/40 bg-status-partial/5 px-3 py-2"
              data-testid="missing-inputs-section"
            >
              <p className="text-xs font-semibold text-foreground">
                Fehlende Angaben ({missingInputs.length})
              </p>
              <ul className="flex flex-col gap-1.5">
                {missingInputs.map((item, index) => (
                  <li key={`${item.label}-${index}`} className="text-xs">
                    <span className="font-medium text-foreground">
                      {item.label}
                    </span>
                    {item.reason && (
                      <span className="text-muted-foreground">
                        {" "}
                        — Warum wichtig: {item.reason}
                      </span>
                    )}
                    {suggestion.target_section && (
                      <span className="text-muted-foreground">
                        {" "}
                        · Innolink-Punkt {suggestion.target_section}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground">
                Nächste Aktion: Ergänzen Sie die Angabe im Text oder prüfen Sie
                sie unter{" "}
                <a
                  href="/anforderungen"
                  className="font-medium text-primary underline-offset-2 hover:underline"
                >
                  Anforderungen
                </a>
                . Die Punkte bleiben nach einer Übernahme als offene Aufgaben
                sichtbar.
              </p>
            </section>
          )}

          {/* v2 — Begründung + Faktenbilanz gebündelt hinter EINEM Aufklapper
              (weniger Overexplain im Standardfluss; Inhalte unverändert). */}
          {(suggestion.rationale || section) && (
            <details className="rounded-md border border-border px-3 py-2">
              <summary className="cursor-pointer text-xs font-medium text-foreground">
                Begründung und Faktenbilanz
              </summary>
              <div className="mt-2 flex flex-col gap-3">
                {suggestion.rationale && (
                  <p className="text-xs text-foreground">{suggestion.rationale}</p>
                )}
                {section && (
                  <div className="grid gap-3 md:grid-cols-2">
                    <ReviewList
                      title="Erhaltene Fakten"
                      items={section.preserved_facts ?? []}
                    />
                    <ReviewList
                      title="Entfernte oder umformulierte Claims"
                      items={section.removed_or_reframed_claims ?? []}
                    />
                    <ReviewList title="Neue Claims" items={section.new_claims ?? []} />
                  </div>
                )}
              </div>
            </details>
          )}

          {/* RUN 4B §6 — Belege: eine Hauptzeile in Nutzersprache, Details
              aufklappbar; Research-Quellen bleiben bewusst getrennt. */}
          <section className="flex flex-col gap-1" data-testid="evidence-usage">
            <p className="text-xs font-medium text-foreground">
              {evidenceCount === 0
                ? "Dieser Vorschlag verwendet keine geprüften Belege."
                : evidenceCount === 1
                  ? "Dieser Vorschlag verwendet 1 geprüften Beleg."
                  : `Dieser Vorschlag verwendet ${evidenceCount} geprüfte Belege.`}
            </p>
            {suggestion.evidence.length > 0 ? (
              <details className="rounded-md border border-border px-3 py-2">
                <summary className="cursor-pointer text-xs font-medium">
                  Belegdetails anzeigen
                </summary>
                <ul className="mt-2 flex flex-col gap-1">
                  {suggestion.evidence.map((e) => (
                    <li
                      key={e.anchor_id}
                      className="rounded border border-border px-2 py-1 text-xs"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-muted-foreground">
                          {e.source_name}
                          {(e.page ?? e.section) && (
                            <>
                              {" · "}
                              {e.page ? `S. ${e.page}` : ""}
                              {e.page && e.section ? " · " : ""}
                              {e.section ? `Abschnitt ${e.section}` : ""}
                            </>
                          )}
                        </span>
                        <Badge
                          variant={
                            e.verification_status === "exact_verified" ? "default" : "outline"
                          }
                        >
                          {VERIFICATION_LABELS[e.verification_status as VerificationStatus] ??
                            e.verification_status}
                        </Badge>
                      </div>
                      <p className="mt-1 line-clamp-2">{e.quote}</p>
                    </li>
                  ))}
                </ul>
              </details>
            ) : (
              evidenceCount > 0 && (
                <p className="text-xs text-muted-foreground">
                  Die Fundstellen-Details stehen für gespeicherte Vorschläge
                  nicht zur Verfügung — die Belege selbst finden Sie im Tab
                  «Quellen».
                </p>
              )
            )}
          </section>

          {suggestion.open_issue_ids.length > 0 && (
            <p className="text-xs text-muted-foreground" data-testid="open-issues">
              Offene Punkte weiterhin zu klären: {suggestion.open_issue_ids.length}
            </p>
          )}

          {(suggestion.research_sources?.length ?? 0) > 0 && (
            <section className="flex flex-col gap-1" data-testid="used-research-sources">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Verwendete Research-Quellen
              </p>
              <p className="text-xs text-muted-foreground">
                Vom Vorschlag referenzierte, durch den Nutzer geprüfte öffentliche Quellen.
                Sie bleiben von formell verifizierten Belegen getrennt.
              </p>
              <ul className="flex flex-col gap-1">
                {suggestion.research_sources?.map((source) => (
                  <li key={source.source_id} className="rounded border border-border px-2 py-1 text-xs">
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-primary underline-offset-2 hover:underline"
                    >
                      {source.title}
                    </a>
                    <p className="text-muted-foreground">
                      Vom Nutzer geprüfte öffentliche Quelle – keine automatische fachliche Freigabe
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <details className="rounded-md border border-border px-3 py-2 text-xs">
            <summary className="cursor-pointer font-medium">Technische Details</summary>
            {/* RUN 4B §2.1 — die Manifest-Kurzbilanz ist Audit-Info und lebt
                nur noch hier (verlagert, nicht gelöscht). */}
            {suggestion.manifest_id && (
              <div
                className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-muted-foreground"
                data-testid="suggestion-manifest-summary"
              >
                <span>Modus: {suggestion.improvement_mode ?? "clearer"}</span>
                <span>Registry-Punkte: {suggestion.used_rule_ids?.length ?? 0}</span>
                <span>Belege: {suggestion.source_version_ids?.length ?? 0}</span>
                <span>Fehlende Angaben: {suggestion.missing_inputs?.length ?? 0}</span>
                {suggestion.stale_reason && <span>Veraltet</span>}
              </div>
            )}
            <dl className="mt-2 grid gap-1 text-muted-foreground">
              <div>Zielabschnitt: {suggestion.target_section ?? "–"}</div>
              <div>Generierungsart: {suggestion.generation_kind ?? "nicht verifiziert"}</div>
              <div>Vorschlags-ID: {suggestion.suggestion_id}</div>
              <div>
                Modellaufruf: {suggestion.generation_kind === "model_generated" ? "Ja" : "Nein"}
              </div>
              {suggestion.generation_kind === "model_generated" && suggestion.proposal && (
                <>
                  <div>Provider: {suggestion.proposal.provider}</div>
                  <div>Modell: {suggestion.proposal.model}</div>
                  <div>Promptversion: {suggestion.proposal.prompt_version}</div>
                </>
              )}
            </dl>
          </details>
        </div>

        {/* Sticky Aktionsleiste (C1/C3). */}
        <SheetFooter className="shrink-0 gap-2 border-t border-border px-6 py-4">
          {reasonOpen ? (
            <div className="flex w-full flex-col gap-2" data-testid="dismiss-reason">
              <p className="text-xs font-medium text-foreground">
                Vorschlag ablehnen — Grund (optional)
              </p>
              <div className="flex flex-wrap gap-1.5">
                {DISMISS_REASONS.map((reason) => (
                  <Button
                    key={reason}
                    type="button"
                    size="xs"
                    variant={reasonChoice === reason ? "secondary" : "outline"}
                    aria-pressed={reasonChoice === reason}
                    onClick={() =>
                      setReasonChoice((previous) => (previous === reason ? null : reason))
                    }
                  >
                    {reason}
                  </Button>
                ))}
              </div>
              <Textarea
                value={reasonText}
                onChange={(e) => setReasonText(e.target.value)}
                placeholder="Eigener Grund (optional)"
                aria-label="Eigener Ablehnungsgrund"
                className="min-h-16 text-sm"
              />
              <div className="flex items-center justify-end gap-2">
                <Button variant="outline" onClick={() => setReasonOpen(false)}>
                  Zurück
                </Button>
                <Button variant="destructive" onClick={confirmDismiss} disabled={accepting}>
                  Ablehnen bestätigen
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex w-full flex-col gap-1.5">
              <div className="flex w-full flex-wrap items-center justify-end gap-2">
                <span className="mr-auto text-[11px] text-muted-foreground">
                  {/* Ein konsistenter Zähler: Auswahl und Gesamtzahl zusammen. */}
                  {onAcceptPartial && !wholeOnly
                    ? `${selected.size} von ${changeCount} Änderungen ausgewählt`
                    : changeCount === 1
                      ? "1 Änderung im Vorschlag"
                      : `${changeCount} Änderungen im Vorschlag`}
                </span>
                <Button
                  variant="ghost"
                  onClick={() => setReasonOpen(true)}
                  disabled={accepting}
                >
                  Vorschlag ablehnen
                </Button>
                {/* RUN 4B §7 — Regenerate als benannte Aktion; bei veralteten
                    Vorschlägen ist es die empfohlene nächste Aktion. */}
                {onRegenerate && (
                  <Button
                    variant="outline"
                    onClick={onRegenerate}
                    disabled={accepting}
                    data-testid="regenerate-suggestion"
                  >
                    Neuen Vorschlag erzeugen
                  </Button>
                )}
                {onEdit && (
                  <Button variant="outline" onClick={onEdit} disabled={accepting}>
                    Eigene Bearbeitung öffnen
                  </Button>
                )}
                {/* v2 — EINE Primäraktion: übernimmt alles (exakt) oder genau
                    die Auswahl; der frühere Zweitbutton entfällt. */}
                <Button
                  onClick={handleAccept}
                  disabled={
                    accepting ||
                    overLimit ||
                    Boolean(suggestion.stale_reason) ||
                    (Boolean(onAcceptPartial) && !wholeOnly && selected.size === 0)
                  }
                >
                  {accepting ? "Wird übernommen …" : "Übernehmen"}
                </Button>
              </div>
              {onAcceptPartial && !wholeOnly && (
                <p className="text-right text-[11px] text-muted-foreground">
                  Sind alle Änderungen ausgewählt, wird der Vorschlag exakt
                  übernommen; sonst genau Ihre Auswahl.
                </p>
              )}
            </div>
          )}
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

function ReviewList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="flex flex-col gap-1">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      {items.length > 0 ? (
        <ul className="list-disc space-y-1 pl-4 text-xs text-foreground">
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">Keine</p>
      )}
    </section>
  )
}
