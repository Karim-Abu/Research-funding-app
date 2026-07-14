"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { VERIFICATION_LABELS, type VerificationStatus } from "@/lib/evidence"
import type { A2Suggestion } from "@/lib/redraft"
import { generationLabel } from "@/lib/generation-kind"

const WARNING_LABELS: Record<string, string> = {
  contains_placeholders:
    "Der Vorschlag enthält Platzhalter für fehlende Angaben — bitte vor der Übernahme prüfen.",
  based_on_unconfirmed_facts:
    "Der Vorschlag stützt sich teilweise auf noch nicht bestätigte (vorgeschlagene) Fakten.",
}

export interface SuggestionReviewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentText: string
  suggestion: A2Suggestion
  onAccept: () => void
  onDismiss: () => void
  accepting?: boolean
}

/**
 * Side-by-side review of an advisory A2 draft suggestion (Solution & Innovation
 * only). The user explicitly accepts ("Übernehmen") or hides it ("Vorschlag
 * ausblenden" — a client-side dismissal, never an audited rejection). No
 * provider/model/confidence is shown; the suggestion is never auto-applied.
 */
export function SuggestionReviewDialog({
  open,
  onOpenChange,
  currentText,
  suggestion,
  onAccept,
  onDismiss,
  accepting = false,
}: SuggestionReviewDialogProps) {
  const overLimit = suggestion.character_count > suggestion.character_limit
  const label = generationLabel(suggestion.generation_kind)
  const section = suggestion.section_result
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>{label} prüfen</DialogTitle>
        </DialogHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <section className="flex flex-col gap-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Aktueller Text
            </p>
            <div
              data-testid="current-text"
              className="max-h-[300px] overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/20 px-3 py-2 text-sm leading-relaxed"
            >
              {currentText || "(leer)"}
            </div>
          </section>
          <section className="flex flex-col gap-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">
              {label}
            </p>
            <div
              data-testid="suggestion-text"
              className="max-h-[300px] overflow-auto whitespace-pre-wrap rounded-md border border-primary/40 bg-primary/5 px-3 py-2 text-sm leading-relaxed"
            >
              {suggestion.suggested_text}
            </div>
          </section>
        </div>

        <p className="text-xs text-muted-foreground" data-testid="character-count">
          {suggestion.character_count} / {suggestion.character_limit} Zeichen
          {overLimit ? " — über dem Limit" : ""}
        </p>

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
            <ReviewList title="Erhaltene Fakten" items={section.preserved_facts} />
            <ReviewList
              title="Entfernte oder umformulierte Claims"
              items={section.removed_or_reframed_claims}
            />
            <ReviewList title="Neue Claims" items={section.new_claims} />
            <ReviewList
              title="Fehlende Inputs"
              items={section.missing_inputs.map((item) =>
                item.reason ? `${item.label}: ${item.reason}` : item.label
              )}
            />
          </div>
        )}

        {suggestion.evidence.length > 0 && (
          <section className="flex flex-col gap-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Verwendete Belege
            </p>
            <ul className="flex flex-col gap-1">
              {suggestion.evidence.map((e) => (
                <li
                  key={e.anchor_id}
                  className="rounded border border-border px-2 py-1 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-muted-foreground">{e.source_name}</span>
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
          </section>
        )}

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
              Vom Vorschlag referenzierte öffentliche Quellen. Eine Fundstelle ist nicht
              automatisch eine fachliche Stützung.
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
                  <p className="text-muted-foreground">Quellenkandidat – fachlich prüfen</p>
                </li>
              ))}
            </ul>
          </section>
        )}

        <details className="rounded-md border border-border px-3 py-2 text-xs">
          <summary className="cursor-pointer font-medium">Technische Details</summary>
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

        <DialogFooter>
          <Button variant="ghost" onClick={onDismiss} disabled={accepting}>
            Vorschlag ausblenden
          </Button>
          <Button onClick={onAccept} disabled={accepting || overLimit}>
            {accepting ? "Wird übernommen …" : "Übernehmen"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
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
