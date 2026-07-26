"use client"

// Wide, read-only market-comparison detail for the Entwurf screen (M10.3).
// Structured as: Gesamturteil (decision) → Marktbild (market picture, statistics
// only) → Lösungslandschaft (solution candidates grouped by type). Only allowed,
// source-qualified formulations can be inserted; disallowed statements are shown
// as a hard block. Insertion writes into the LOCAL editor buffer only (HITL:
// the user reviews and saves; the normal onChange/version/undo path is used).

import * as React from "react"
import { Info, Lock } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { MarketComparisonBasis } from "@/components/editor/market-comparison-basis"
import { MarketGapList, MarketPictureList } from "@/components/editor/market-blocks"
import { cn } from "@/lib/utils"
import {
  CANDIDATE_TYPE_ORDER,
  JUDGMENT_INSUFFICIENT_HINT,
  MARKET_HYPOTHESIS_NOTE,
  MARKET_STALE_BADGE,
  MARKET_TONE_STYLE,
  candidateTypeOf,
  judgmentToneClass,
  marketGaps,
  marketPictureFrom,
  marketStaleExplanation,
  marketWorkspaceStatus,
} from "@/lib/market-view"
// CANDIDATE_TYPE_LABELS/JUDGMENT_STATUS_LABELS are consumed directly below.
import {
  CANDIDATE_TYPE_LABELS,
  CONFIDENCE_LABELS,
  CONFIDENCE_STYLE,
  ITEM_CATEGORY_LABELS,
  ITEM_STATUS_LABELS,
  JUDGMENT_STATUS_LABELS,
  type CompetitionJudgmentDto,
  type MarketComparisonDto,
  type MarketComparisonItemDto,
  type SolutionLandscapeCandidateDto,
} from "@/lib/market-comparison"

const INSERT_BLOCKED_HINT =
  "Nur belegte, auf den Suchraum eingeschränkte Aussagen können übernommen werden."
const SOURCE_HINT = "gestützt auf die im Vergleich verwendeten geprüften öffentlichen Quellen"

interface MarketComparisonSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  comparison: MarketComparisonDto | null
  /** Inserts a source-qualified formulation into the local draft buffer (unsaved). */
  onInsertText: (text: string) => void
}

export function MarketComparisonSheet({
  open,
  onOpenChange,
  comparison,
  onInsertText,
}: MarketComparisonSheetProps) {
  const [inserted, setInserted] = React.useState(false)

  React.useEffect(() => {
    if (!open) setInserted(false)
  }, [open])

  // Marktaussagen (Marktgrösse, Kundenprobleme) sind KEINE Lösungskandidaten
  // und dürfen nie in einer Anbieter-/Alternativen-Tabelle stehen — dieselbe
  // Trennung wie in der Quellen-Sektion (lib/market-comparison, CANDIDATE_TYPE).
  const items = (comparison?.items ?? []).filter(
    (item) => candidateTypeOf(item) !== null
  )
  const hasMarketClaims = (comparison?.items ?? []).some(
    (item) => candidateTypeOf(item) === null
  )
  const status = marketWorkspaceStatus(comparison)
  const picture = marketPictureFrom(comparison)
  const judgment = comparison?.competition_judgment ?? null
  const landscape = comparison?.solution_landscape ?? null
  const scopeStale = comparison?.scope_stale ?? false
  const staleExplanation = marketStaleExplanation(comparison)

  function insert(text: string) {
    onInsertText(`${text} (${SOURCE_HINT})`)
    setInserted(true)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="gap-0 overflow-y-auto data-[side=right]:w-[940px] data-[side=right]:max-w-[95vw] data-[side=right]:sm:max-w-[95vw]"
        data-testid="market-comparison-sheet"
      >
        <SheetHeader>
          <SheetTitle>Markt- und Konkurrenzvergleich</SheetTitle>
          <SheetDescription>{MARKET_HYPOTHESIS_NOTE}</SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-4 px-4 pb-6">
          <div className="flex flex-wrap items-center gap-2">
            <span
              data-testid="market-sheet-status"
              className={cn(
                "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                MARKET_TONE_STYLE[status.tone]
              )}
            >
              {status.label}
            </span>
            {status.hint && <span className="text-[11px] text-muted-foreground">{status.hint}</span>}
            {scopeStale && (
              <span
                data-testid="market-sheet-stale"
                className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium", MARKET_TONE_STYLE.attention)}
              >
                {MARKET_STALE_BADGE}
              </span>
            )}
          </div>
          {staleExplanation && (
            <p className="-mt-2 text-[11px] text-muted-foreground">{staleExplanation}</p>
          )}

          {comparison?.comparison_basis && <MarketComparisonBasis basis={comparison.comparison_basis} />}

          {inserted && (
            <p role="status" className="rounded-md border border-status-fulfilled/30 bg-status-fulfilled/8 px-3 py-2 text-[11px] text-foreground">
              Aussage eingefügt — noch nicht gespeichert. Prüfen und speichern Sie den Text im Editor.
            </p>
          )}

          {/* Drei Abschnitte, mehr nicht: Ergebnis → Gefundene Lösungen → Was
              noch fehlt. Marktaussagen und Quellen liegen dahinter/eine Ebene
              tiefer (Marktbild eingeklappt, «Quellen öffnen» im Footer). */}
          <section data-testid="market-result" className="flex flex-col gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Ergebnis</h2>
            {judgment ? (
              <JudgmentCard judgment={judgment} onInsert={insert} />
            ) : (
              items.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  Noch keine Vergleichseinträge. Erstellen Sie den Vergleich unter Quellen aus importierten öffentlichen Quellen.
                </p>
              )
            )}
          </section>

          <section data-testid="market-solutions" className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Gefundene Lösungen</h2>

            {/* Marktbild — Marktinformationen, keine Lösungskandidaten; per Default eingeklappt. */}
            {picture.points.length > 0 && (
              <details data-testid="market-picture" className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
                <summary className="cursor-pointer text-xs font-semibold text-foreground">Marktbild (Marktinformationen)</summary>
                <p className="mb-1 mt-1 text-[11px] text-muted-foreground">Marktinformationen — keine Wettbewerber.</p>
                <MarketPictureList points={picture.points} />
              </details>
            )}

            {/* Lösungslandschaft (Kandidaten nach Typ; getrennt vom Marktbild). */}
            {landscape && landscape.candidates.length > 0 ? (
              <div data-testid="market-solution-landscape" className="flex flex-col gap-3">
                {CANDIDATE_TYPE_ORDER.map((type) => {
                  const group = landscape.candidates.filter((c) => c.candidate_type === type)
                  if (group.length === 0) return null
                  return (
                    <div key={type}>
                      <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                        {CANDIDATE_TYPE_LABELS[type]} ({group.length})
                      </p>
                      <ul className="flex flex-col gap-2">
                        {group.map((candidate) => (
                          <CandidateCard key={candidate.item_id} candidate={candidate} onInsert={insert} />
                        ))}
                      </ul>
                    </div>
                  )
                })}
              </div>
            ) : items.length > 0 ? (
              <LegacyTable items={items} onInsert={insert} />
            ) : (
              hasMarketClaims && (
                <p className="text-xs text-status-partial" role="status" data-testid="market-only-claims">
                  Im Suchumfang wurden bisher nur Marktaussagen gefunden, aber keine
                  vergleichbaren Lösungen. Die offenen Evidenzlücken zeigen, was fehlt.
                </p>
              )
            )}
          </section>

          <section data-testid="market-gaps-section" className="flex flex-col gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Was noch fehlt</h2>
            <MarketGapList gaps={marketGaps(comparison)} limit={3} compact testId="market-gaps" />
          </section>

          <div className="flex items-center gap-2 border-t border-border pt-3">
            <Button size="sm" variant="ghost" render={<a href="/quellen" />} nativeButton={false}>
              Quellen öffnen
            </Button>
            <span className="text-[11px] text-muted-foreground">
              Einträge übernehmen/ablehnen erfolgt unter Quellen.
            </span>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function JudgmentCard({
  judgment,
  onInsert,
}: {
  judgment: CompetitionJudgmentDto
  onInsert: (text: string) => void
}) {
  return (
    <section data-testid="market-judgment" className="flex flex-col gap-2 rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-foreground">Gesamturteil</h3>
        <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium", judgmentToneClass(judgment.status))}>
          {JUDGMENT_STATUS_LABELS[judgment.status]}
        </span>
      </div>
      <p className="text-xs text-foreground">{judgment.rationale}</p>
      <p className="text-[11px] text-muted-foreground">{judgment.scope_summary}</p>
      {judgment.status === "insufficient_evidence" && (
        <p className="text-[11px] text-muted-foreground" data-testid="market-judgment-insufficient-hint">
          {JUDGMENT_INSUFFICIENT_HINT}
        </p>
      )}

      {judgment.key_overlaps.length > 0 && (
        <div className="text-[11px]">
          <span className="font-medium text-foreground">Überschneidungen: </span>
          <span className="text-muted-foreground">{judgment.key_overlaps.join(" · ")}</span>
        </div>
      )}
      {judgment.evidenced_differentiators.length > 0 && (
        <div className="text-[11px]">
          <p className="font-medium text-foreground">Belegte Differenzierung</p>
          <ul className="list-disc pl-4 text-muted-foreground">
            {judgment.evidenced_differentiators.map((d, i) => <li key={i}>{d}</li>)}
          </ul>
        </div>
      )}
      {judgment.plausible_unverified_differentiators.length > 0 && (
        <div className="text-[11px]">
          <p className="font-medium text-status-partial">Plausibel, aber noch ungeprüft</p>
          <ul className="list-disc pl-4 text-muted-foreground">
            {judgment.plausible_unverified_differentiators.map((d, i) => <li key={i}>{d}</li>)}
          </ul>
        </div>
      )}

      {/* Antragsfähige (zulässige) Aussagen — nur wenn belegt & Suchraum aktuell. */}
      {judgment.allowed_formulations.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <p className="text-[11px] font-medium text-foreground">Für den Antrag zulässige Aussagen</p>
          {judgment.allowed_formulations.map((text, i) => (
            <div key={i} className="flex items-start justify-between gap-2 rounded-md border border-border px-2.5 py-1.5">
              <span className="text-[11px] text-foreground">{text}</span>
              <Button
                size="xs"
                variant="outline"
                disabled={!judgment.can_insert_into_application}
                title={judgment.can_insert_into_application ? undefined : INSERT_BLOCKED_HINT}
                onClick={() => onInsert(text)}
              >
                Übernehmen
              </Button>
            </div>
          ))}
          {!judgment.can_insert_into_application && (
            <p className="text-[11px] text-muted-foreground">{INSERT_BLOCKED_HINT}</p>
          )}
        </div>
      )}

      {/* Overclaim-Schutz: sichtbarer Sperr-Block. */}
      {judgment.disallowed_formulations.length > 0 && (
        <div data-testid="market-disallowed" className="rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-2">
          <p className="flex items-center gap-1.5 text-[11px] font-medium text-destructive">
            <Lock className="size-3" /> Nicht zulässige Aussagen (nicht übernehmbar)
          </p>
          <ul className="mt-1 list-disc pl-4 text-[11px] text-muted-foreground">
            {judgment.disallowed_formulations.map((text, i) => <li key={i}>{text}</li>)}
          </ul>
        </div>
      )}

      {/* Die Evidenzlücken stehen einmal je Fläche — als eigener Abschnitt
          unter dem Urteil, nicht zusätzlich hier drin (siehe `marketGaps`). */}
    </section>
  )
}

function CandidateCard({
  candidate,
  onInsert,
}: {
  candidate: SolutionLandscapeCandidateDto
  onInsert: (text: string) => void
}) {
  const insertable = candidate.allowed_formulations.length > 0 && candidate.source_scope_ok
  return (
    <li className="rounded-md border border-border px-3 py-2.5">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold text-foreground">{candidate.name}</p>
        <Badge variant="secondary" className={CONFIDENCE_STYLE[candidate.confidence_label]}>
          {CONFIDENCE_LABELS[candidate.confidence_label]}
        </Badge>
      </div>
      {candidate.overlaps.length > 0 && (
        <p className="mt-1 text-[11px] text-muted-foreground">
          <span className="font-medium text-foreground">Überschneidungen: </span>
          {candidate.overlaps.join(" · ")}
        </p>
      )}
      {candidate.evidencing_differentiators.length > 0 && (
        <p className="mt-1 text-[11px] text-muted-foreground">
          <span className="font-medium text-foreground">Belegte Differenzierung: </span>
          {candidate.evidencing_differentiators.join(" ")}
        </p>
      )}
      {candidate.unverified_differentiators.length > 0 && (
        <p className="mt-1 text-[11px] text-muted-foreground">
          <span className="font-medium text-status-partial">Plausibel (ungeprüft): </span>
          {candidate.unverified_differentiators.join(" ")}
        </p>
      )}
      {candidate.evidence_quotes.length > 0 && (
        <blockquote className="mt-1 border-l-2 border-border pl-2 text-[11px] italic text-muted-foreground">
          „{candidate.evidence_quotes[0].quote}“
        </blockquote>
      )}
      {candidate.allowed_formulations.map((text, i) => (
        <Button
          key={i}
          size="xs"
          variant="outline"
          className="mt-1.5"
          disabled={!insertable}
          title={insertable ? undefined : INSERT_BLOCKED_HINT}
          onClick={() => onInsert(text)}
        >
          Als Argument übernehmen
        </Button>
      ))}
    </li>
  )
}

// Fallback for comparisons that predate the analytical landscape (no
// solution_landscape on the response): the original per-item table.
function LegacyTable({
  items,
  onInsert,
}: {
  items: MarketComparisonItemDto[]
  onInsert: (text: string) => void
}) {
  const insertableOf = (item: MarketComparisonItemDto) =>
    item.confidence_label === "source_backed" &&
    item.status !== "rejected" &&
    Boolean(item.differentiation_relevance?.trim())
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr className="border-b border-border text-muted-foreground">
            <th className="py-2 pr-3 font-medium">Wettbewerber / Lösung</th>
            <th className="py-2 pr-3 font-medium">Differenzierung</th>
            <th className="py-2 pr-3 font-medium">Quelle</th>
            <th className="py-2 pr-3 font-medium">Status</th>
            <th className="py-2 font-medium"><span className="sr-only">Aktion</span></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const insertable = insertableOf(item)
            return (
              <tr key={item.item_id} className="border-b border-border/60 align-top">
                <td className="py-2 pr-3">
                  <p className="font-medium text-foreground">{item.name}</p>
                  <p className="text-[11px] text-muted-foreground">{ITEM_CATEGORY_LABELS[item.category]}</p>
                </td>
                <td className="py-2 pr-3 text-muted-foreground">{item.differentiation_relevance?.trim() || "—"}</td>
                <td className="py-2 pr-3">
                  {item.evidence_quotes.length > 0 ? (
                    <blockquote className="border-l-2 border-border pl-2 text-[11px] italic text-muted-foreground">
                      „{item.evidence_quotes[0].quote}“
                    </blockquote>
                  ) : (
                    <span className="text-[11px] text-muted-foreground">Kein belegtes Zitat</span>
                  )}
                </td>
                <td className="py-2 pr-3">
                  <Badge variant="secondary" className={CONFIDENCE_STYLE[item.confidence_label]}>
                    {CONFIDENCE_LABELS[item.confidence_label]}
                  </Badge>
                  {item.status !== "proposed" && (
                    <span className="block text-[11px] text-muted-foreground">{ITEM_STATUS_LABELS[item.status]}</span>
                  )}
                </td>
                <td className="py-2">
                  <Button
                    size="xs"
                    variant="outline"
                    disabled={!insertable}
                    title={insertable ? undefined : INSERT_BLOCKED_HINT}
                    onClick={() => onInsert(`Abgrenzung zu ${item.name}: ${item.differentiation_relevance?.trim() ?? ""}`)}
                  >
                    Als Argument übernehmen
                  </Button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
