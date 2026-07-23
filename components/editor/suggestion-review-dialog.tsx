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
  type DiffSegment,
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
}

// C2 — Badge-Text je Segmentart: die Klassifikation ist nie nur Farbe (a11y).
const KIND_LABELS: Record<DiffSegment["kind"], string> = {
  beibehalten: "Beibehalten",
  entfernt: "Entfernt",
  hinzugefuegt: "Neu",
  umformuliert: "Umformuliert",
}

const KIND_BADGE_CLASS: Record<DiffSegment["kind"], string> = {
  beibehalten: "border-border bg-muted/40 text-muted-foreground",
  entfernt: "border-destructive/30 bg-destructive/10 text-destructive",
  hinzugefuegt: "border-status-fulfilled/40 bg-status-fulfilled/10 text-status-fulfilled",
  umformuliert: "border-status-partial/40 bg-status-partial/10 text-status-partial",
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
  accepting = false,
}: SuggestionReviewDialogProps) {
  const overLimit = suggestion.character_count > suggestion.character_limit
  const label = generationLabel(suggestion.generation_kind)
  const section = suggestion.section_result
  const chips = rationaleChips(suggestion)
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

  // Auswahl/Ablehnungsformular je Vorschlag zurücksetzen.
  React.useEffect(() => {
    setSelected(new Set())
    setReasonOpen(false)
    setReasonChoice(null)
    setReasonText("")
  }, [suggestion.suggestion_id])

  function toggleSegment(index: number) {
    setSelected((previous) => {
      const next = new Set(previous)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  function confirmDismiss() {
    const reason = [reasonChoice, reasonText.trim()].filter(Boolean).join(" — ")
    onDismiss(reason || undefined)
  }

  function acceptSelected() {
    if (!onAcceptPartial || selected.size === 0) return
    onAcceptPartial(applySegments(currentText, segments, selected))
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
          {/* Fachliche Kurzbilanz VOR dem Diff: was blieb, was fiel weg, was
              fehlt, welche Quellen — plus Textumfang alt → neu. */}
          {section && (
            <div
              className="flex flex-wrap gap-1.5"
              data-testid="suggestion-summary"
            >
              {/* Fallbacks: Feld-Level-Vorschläge tragen nicht alle
                  Section-Listen — fehlende Liste = 0, nie ein Renderfehler. */}
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
          {chips.length > 0 && (
            <div className="flex flex-wrap gap-1.5" data-testid="rationale-chips">
              {chips.map((chip) => (
                <span
                  key={chip.text}
                  className={cn(
                    "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
                    chip.tone === "entfernt" &&
                      "border-status-partial/40 bg-status-partial/10 text-status-partial",
                    chip.tone === "neu" &&
                      "border-primary/30 bg-primary/10 text-primary",
                    chip.tone === "offen" &&
                      "border-border bg-muted/50 text-muted-foreground"
                  )}
                >
                  {chip.text}
                </span>
              ))}
            </div>
          )}

          {/* C2 — echter Satz-Diff, side-by-side, vertikal gross. */}
          <div className="grid min-w-0 gap-4 md:grid-cols-2">
            <section className="flex min-w-0 flex-col gap-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Aktueller Text
              </p>
              <div
                data-testid="current-text"
                className="flex flex-col gap-1.5 rounded-md border border-border bg-muted/20 px-3 py-2"
              >
                {segments.filter((s) => s.before !== null).length === 0 && (
                  <p className="text-sm text-muted-foreground">(leer)</p>
                )}
                {segments.map((segment, index) =>
                  segment.before === null ? null : (
                    <div key={`before-${index}`} className="flex flex-col gap-0.5">
                      {segment.kind !== "beibehalten" && (
                        <span
                          className={cn(
                            "inline-flex w-fit items-center rounded-full border px-1.5 py-px text-[10px] font-medium",
                            KIND_BADGE_CLASS[segment.kind]
                          )}
                        >
                          {KIND_LABELS[segment.kind]}
                        </span>
                      )}
                      <p
                        className={cn(
                          "whitespace-pre-wrap text-sm leading-relaxed",
                          segment.kind === "entfernt" &&
                            "text-destructive line-through decoration-destructive/60"
                        )}
                      >
                        {segment.kind === "umformuliert" && segment.words
                          ? segment.words
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
                          : segment.before}
                      </p>
                    </div>
                  )
                )}
              </div>
            </section>

            <section className="flex min-w-0 flex-col gap-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                {label}
              </p>
              <div
                data-testid="suggestion-text"
                className="flex flex-col gap-1.5 rounded-md border border-primary/40 bg-primary/5 px-3 py-2"
              >
                {segments.map((segment, index) =>
                  segment.after === null ? (
                    // Streichungen sind rechts als übernehmbare Änderung wählbar.
                    segment.kind === "entfernt" ? (
                      <div key={`after-${index}`} className="flex flex-col gap-0.5">
                        <div className="flex w-fit items-center gap-1.5 text-[11px] text-muted-foreground">
                          {!wholeOnly && (
                            <input
                              type="checkbox"
                              checked={selected.has(index)}
                              onChange={() => toggleSegment(index)}
                              aria-label={`Streichung übernehmen: ${segment.before ?? ""}`}
                            />
                          )}
                          <span
                            className={cn(
                              "inline-flex items-center rounded-full border px-1.5 py-px text-[10px] font-medium",
                              KIND_BADGE_CLASS.entfernt
                            )}
                          >
                            Streichung übernehmen
                          </span>
                        </div>
                      </div>
                    ) : null
                  ) : (
                    <div key={`after-${index}`} className="flex flex-col gap-0.5">
                      {segment.kind !== "beibehalten" && (
                        <div className="flex w-fit items-center gap-1.5 text-[11px] text-muted-foreground">
                          {!wholeOnly && (
                            <input
                              type="checkbox"
                              checked={selected.has(index)}
                              onChange={() => toggleSegment(index)}
                              aria-label={`Änderung übernehmen: ${segment.after}`}
                            />
                          )}
                          <span
                            className={cn(
                              "inline-flex items-center rounded-full border px-1.5 py-px text-[10px] font-medium",
                              KIND_BADGE_CLASS[segment.kind]
                            )}
                          >
                            {KIND_LABELS[segment.kind]}
                          </span>
                        </div>
                      )}
                      <p className="whitespace-pre-wrap text-sm leading-relaxed">
                        {segment.kind === "umformuliert" && segment.words
                          ? segment.words
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
                          : segment.after}
                      </p>
                    </div>
                  )
                )}
              </div>
            </section>
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

          {suggestion.warnings.map((w) => (
            <p
              key={w}
              role="status"
              data-testid={`warning-${w}`}
              className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900"
            >
              {WARNING_LABELS[w] ?? w}
            </p>
          ))}

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

          {suggestion.rationale && (
            <section className="flex flex-col gap-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Begründung
              </p>
              <p className="text-xs text-foreground">{suggestion.rationale}</p>
            </section>
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
            <div className="flex w-full flex-wrap items-center justify-end gap-2">
              <span className="mr-auto text-[11px] text-muted-foreground">
                {changeCount === 1
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
              {onEdit && (
                <Button variant="outline" onClick={onEdit} disabled={accepting}>
                  Eigene Bearbeitung öffnen
                </Button>
              )}
              {onAcceptPartial && !wholeOnly && (
                <Button
                  variant="outline"
                  onClick={acceptSelected}
                  disabled={accepting || selected.size === 0}
                >
                  Ausgewählte übernehmen ({selected.size})
                </Button>
              )}
              <Button
                onClick={onAccept}
                disabled={accepting || overLimit || Boolean(suggestion.stale_reason)}
              >
                {accepting ? "Wird übernommen …" : "Übernehmen"}
              </Button>
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
