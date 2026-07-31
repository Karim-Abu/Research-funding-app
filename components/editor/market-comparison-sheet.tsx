"use client"

// Wide, read-only market-comparison detail for the Entwurf screen (M10.3).
// Structured as: Ergebnis (die eine Antwort) → Gefundene Lösungen → Was noch
// fehlt. Kontext (Vergleichsbasis, Marktbild) und generische Sperrlisten liegen
// hinter Aufklappern, damit die Antwort die Fläche trägt. Only allowed,
// source-qualified formulations can be inserted; disallowed statements stay
// visible one click away. Insertion writes into the LOCAL editor buffer only
// (HITL: the user reviews and saves; the normal onChange/version/undo path).

import * as React from "react"
import { Lock } from "lucide-react"
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
import {
  MarketDisclosure,
  MarketGapList,
  MarketPictureList,
} from "@/components/editor/market-blocks"
import { cn } from "@/lib/utils"
import {
  CANDIDATE_TYPE_ORDER,
  MARKET_HYPOTHESIS_NOTE,
  MARKET_TONE_STYLE,
  candidateTypeOf,
  marketGaps,
  marketPictureFrom,
  marketUiState,
  type MarketUiState,
} from "@/lib/market-view"
import {
  CANDIDATE_TYPE_LABELS,
  CONFIDENCE_LABELS,
  CONFIDENCE_STYLE,
  ITEM_CATEGORY_LABELS,
  ITEM_STATUS_LABELS,
  type CompetitionJudgmentDto,
  type MarketComparisonDto,
  type MarketComparisonItemDto,
  type SolutionLandscapeCandidateDto,
} from "@/lib/market-comparison"

const INSERT_BLOCKED_HINT =
  "Noch keine Aussage für den Antrag übernehmbar — die geprüfte Vergleichsabdeckung trägt sie nicht. Erst weitere Recherche, dann Vergleich neu erstellen."
const SOURCE_HINT = "gestützt auf die im Vergleich verwendeten geprüften öffentlichen Quellen"

// Eine Typografie-Ebene je Bedeutung — vorher standen Antwort, Beleg und
// Randnotiz alle in 11 px nebeneinander.
const SECTION_HEADING = "text-sm font-semibold text-foreground"
const GROUP_LABEL = "text-xs font-medium text-muted-foreground"

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
  const ui = marketUiState(comparison)
  const picture = marketPictureFrom(comparison)
  const judgment = comparison?.competition_judgment ?? null
  const landscape = comparison?.solution_landscape ?? null

  function insert(text: string) {
    onInsertText(`${text} (${SOURCE_HINT})`)
    setInserted(true)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="gap-0 overflow-y-auto data-[side=right]:w-[880px] data-[side=right]:max-w-[95vw] data-[side=right]:sm:max-w-[95vw]"
        data-testid="market-comparison-sheet"
      >
        <SheetHeader className="gap-2 border-b border-border pb-4">
          <div className="flex flex-wrap items-center gap-2 pr-10">
            <SheetTitle>Markt- und Konkurrenzvergleich</SheetTitle>
            {/* Eine Statusaussage je Fläche — identisch abgeleitet wie in
                Quellen-Karte und Editor-Rail. */}
            <span
              data-testid="market-sheet-status"
              className={cn(
                "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium",
                MARKET_TONE_STYLE[ui.tone]
              )}
            >
              {ui.label}
            </span>
          </div>
          <SheetDescription className="text-xs leading-relaxed">
            {MARKET_HYPOTHESIS_NOTE}
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-6 px-4 pt-4 pb-8">
          {inserted && (
            <p
              role="status"
              className="rounded-md border border-status-fulfilled/30 bg-status-fulfilled/8 px-3 py-2 text-xs leading-relaxed text-foreground"
            >
              Aussage eingefügt — noch nicht gespeichert. Prüfen und speichern Sie den Text im Editor.
            </p>
          )}

          {/* Kontext, eine Zeile: wogegen verglichen wurde. Details auf Wunsch. */}
          {comparison?.comparison_basis && (
            <MarketComparisonBasis basis={comparison.comparison_basis} collapsible />
          )}

          {/* Drei Abschnitte, mehr nicht: Ergebnis → Gefundene Lösungen → Was
              noch fehlt. Marktbild und Quellen liegen eine Ebene tiefer. */}
          <section data-testid="market-result" className="flex flex-col gap-2.5">
            <h2 className={SECTION_HEADING}>Ergebnis</h2>
            {comparison ? (
              <ResultCard ui={ui} judgment={judgment} onInsert={insert} />
            ) : (
              <p className="text-sm leading-relaxed text-muted-foreground">
                Noch keine Vergleichseinträge. Erstellen Sie den Vergleich unter Quellen aus importierten öffentlichen Quellen.
              </p>
            )}
          </section>

          <section data-testid="market-solutions" className="flex flex-col gap-3">
            <h2 className={SECTION_HEADING}>Gefundene Lösungen</h2>

            {/* Lösungslandschaft (Kandidaten nach Typ; getrennt vom Marktbild). */}
            {landscape && landscape.candidates.length > 0 ? (
              <div data-testid="market-solution-landscape" className="flex flex-col gap-4">
                {CANDIDATE_TYPE_ORDER.map((type) => {
                  const group = landscape.candidates.filter((c) => c.candidate_type === type)
                  if (group.length === 0) return null
                  return (
                    <div key={type} className="flex flex-col gap-2">
                      <p className={GROUP_LABEL}>
                        {CANDIDATE_TYPE_LABELS[type]} ({group.length})
                      </p>
                      <ul className="flex flex-col gap-2">
                        {group.map((candidate) => (
                          <CandidateCard
                            key={candidate.item_id}
                            candidate={candidate}
                            canInsert={ui.canInsert}
                            onInsert={insert}
                          />
                        ))}
                      </ul>
                    </div>
                  )
                })}
              </div>
            ) : items.length > 0 ? (
              <LegacyTable items={items} canInsert={ui.canInsert} onInsert={insert} />
            ) : (
              hasMarketClaims && (
                <p
                  className="text-xs leading-relaxed text-status-partial"
                  role="status"
                  data-testid="market-only-claims"
                >
                  Im Suchumfang wurden bisher nur Marktaussagen gefunden, aber keine
                  vergleichbaren Lösungen. Die offenen Evidenzlücken zeigen, was fehlt.
                </p>
              )
            )}

            {/* Marktbild — Marktinformationen, keine Lösungskandidaten. */}
            {picture.points.length > 0 && (
              <MarketDisclosure
                testId="market-picture"
                summary="Marktbild (Marktinformationen, keine Wettbewerber)"
              >
                <MarketPictureList points={picture.points} />
              </MarketDisclosure>
            )}
          </section>

          <section data-testid="market-gaps-section" className="flex flex-col gap-2.5">
            <h2 className={SECTION_HEADING}>Was noch fehlt</h2>
            {/* Der Abschnittskopf benennt die Liste bereits — kein zweiter Titel. */}
            <MarketGapList
              gaps={marketGaps(comparison)}
              limit={3}
              label={null}
              testId="market-gaps"
            />
          </section>

          <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
            <Button size="sm" variant="outline" render={<a href="/quellen" />} nativeButton={false}>
              Quellen öffnen
            </Button>
            <span className="text-xs text-muted-foreground">
              Einträge übernehmen/ablehnen erfolgt unter Quellen.
            </span>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

/**
 * Die eine Antwort: Ergebnissatz, Suchumfang, nächster Schritt — und nur wenn
 * die Abdeckung sie trägt, die übernehmbare Formulierung.
 *
 * Der Ergebnissatz kommt aus `marketUiState` (nicht direkt aus dem Urteil):
 * bei veraltetem Suchraum oder zu schmaler Quellenlage steht dort die ehrliche
 * Aussage, während `judgment.rationale` noch den alten Befund tragen würde.
 */
function ResultCard({
  ui,
  judgment,
  onInsert,
}: {
  ui: MarketUiState
  judgment: CompetitionJudgmentDto | null
  onInsert: (text: string) => void
}) {
  const allowed = judgment?.allowed_formulations ?? []
  const disallowed = judgment?.disallowed_formulations ?? []
  const details = judgment
    ? judgment.key_overlaps.length > 0 ||
      judgment.evidenced_differentiators.length > 0 ||
      judgment.plausible_unverified_differentiators.length > 0
    : false

  return (
    <section
      data-testid="market-judgment"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card px-4 py-3.5"
    >
      <div className="flex flex-col gap-1.5">
        <p className="text-sm leading-relaxed text-foreground">{ui.summary}</p>
        {judgment?.scope_summary && (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {judgment.scope_summary}
          </p>
        )}
        <p className="text-xs leading-relaxed text-muted-foreground">
          Nächster Schritt: {ui.nextStep}
        </p>
      </div>

      {details && judgment && (
        <div className="flex flex-col gap-2 border-t border-border pt-3">
          {judgment.key_overlaps.length > 0 && (
            <p className="text-xs leading-relaxed">
              <span className="font-medium text-foreground">Überschneidungen: </span>
              <span className="text-muted-foreground">{judgment.key_overlaps.join(" · ")}</span>
            </p>
          )}
          {judgment.evidenced_differentiators.length > 0 && (
            <div className="text-xs">
              <p className="font-medium text-foreground">Belegte Differenzierung</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 leading-relaxed text-muted-foreground">
                {judgment.evidenced_differentiators.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            </div>
          )}
          {judgment.plausible_unverified_differentiators.length > 0 && (
            <div className="text-xs">
              <p className="font-medium text-status-partial">Plausibel, aber noch ungeprüft</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 leading-relaxed text-muted-foreground">
                {judgment.plausible_unverified_differentiators.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Antragsfähige Aussagen erscheinen nur, wenn die Vergleichsabdeckung
          sie trägt. Eine Aussage wie «es wurde nichts Gleichwertiges
          identifiziert» ist bei schmaler Basis eine Überbehauptung — dann wird
          gar nichts zur Übernahme angeboten (statt eines deaktivierten
          Buttons, der zum Nachfassen einlädt). */}
      {ui.canInsert && allowed.length > 0 && (
        <div
          className="flex flex-col gap-2 border-t border-border pt-3"
          data-testid="market-allowed-formulations"
        >
          <p className="text-xs font-medium text-foreground">
            {allowed.length === 1
              ? "Für den Antrag zulässige Aussage"
              : "Für den Antrag zulässige Aussagen"}
          </p>
          {allowed.map((text, i) => (
            <div
              key={i}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
            >
              {/* Wortgleich mit dem Ergebnissatz oben? Dann nicht zweimal
                  denselben Satz zeigen (R2), nur die Übernahme anbieten. */}
              <span className="min-w-0 flex-1 text-xs leading-relaxed text-foreground">
                {isSameStatement(text, ui.summary)
                  ? "Der Ergebnissatz oben — unverändert übernehmbar."
                  : text}
              </span>
              <Button size="sm" variant="outline" onClick={() => onInsert(text)}>
                Übernehmen
              </Button>
            </div>
          ))}
        </div>
      )}
      {!ui.canInsert && (
        <p
          className="border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground"
          data-testid="market-insert-blocked"
        >
          {INSERT_BLOCKED_HINT}
        </p>
      )}

      {/* Overclaim-Schutz: die Liste ist generisch und immer gleich — sie bleibt
          einen Klick entfernt vollständig einsehbar, verdrängt aber nicht das
          Ergebnis. */}
      {disallowed.length > 0 && (
        <MarketDisclosure
          testId="market-disallowed"
          tone="blocked"
          icon={<Lock aria-hidden className="size-3 shrink-0" />}
          summary="Nicht zulässige Aussagen"
          count={disallowed.length}
        >
          <p className="text-xs text-muted-foreground">
            Diese Formulierungen sind durch den Suchumfang nicht gedeckt und nicht übernehmbar.
          </p>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-xs leading-relaxed text-muted-foreground">
            {disallowed.map((text, i) => <li key={i}>{text}</li>)}
          </ul>
        </MarketDisclosure>
      )}

      {/* Die Evidenzlücken stehen einmal je Fläche — als eigener Abschnitt
          unter dem Urteil, nicht zusätzlich hier drin (siehe `marketGaps`). */}
    </section>
  )
}

/** Satzvergleich ohne Interpunktions-/Whitespace-Rauschen. */
function isSameStatement(a: string, b: string): boolean {
  const normalize = (value: string) =>
    value.replace(/\s+/g, " ").replace(/[.!?]+$/, "").trim().toLowerCase()
  return normalize(a) === normalize(b)
}

function CandidateCard({
  candidate,
  canInsert,
  onInsert,
}: {
  candidate: SolutionLandscapeCandidateDto
  /** Trägt die Gesamtabdeckung eine Antragsaussage? (marketUiState) */
  canInsert: boolean
  onInsert: (text: string) => void
}) {
  // Die Gesamtabdeckung entscheidet mit: reicht sie nicht, darf auch kein
  // Einzelargument in den Antrag (CLAUDEX §2 — HITL, keine Überbehauptung).
  const insertable =
    canInsert && candidate.allowed_formulations.length > 0 && candidate.source_scope_ok
  return (
    <li className="flex flex-col gap-1.5 rounded-md border border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="text-sm font-medium text-foreground">{candidate.name}</p>
        <Badge variant="secondary" className={CONFIDENCE_STYLE[candidate.confidence_label]}>
          {CONFIDENCE_LABELS[candidate.confidence_label]}
        </Badge>
      </div>
      {candidate.overlaps.length > 0 && (
        <p className="text-xs leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">Überschneidungen: </span>
          {candidate.overlaps.join(" · ")}
        </p>
      )}
      {candidate.evidencing_differentiators.length > 0 && (
        <p className="text-xs leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">Belegte Differenzierung: </span>
          {candidate.evidencing_differentiators.join(" ")}
        </p>
      )}
      {candidate.unverified_differentiators.length > 0 && (
        <p className="text-xs leading-relaxed text-muted-foreground">
          <span className="font-medium text-status-partial">Plausibel (ungeprüft): </span>
          {candidate.unverified_differentiators.join(" ")}
        </p>
      )}
      {candidate.evidence_quotes.length > 0 && (
        <blockquote className="border-l-2 border-border pl-3 text-xs italic leading-relaxed text-muted-foreground">
          „{candidate.evidence_quotes[0].quote}“
        </blockquote>
      )}
      {insertable &&
        candidate.allowed_formulations.map((text, i) => (
          <Button
            key={i}
            size="sm"
            variant="outline"
            className="mt-0.5 w-fit"
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
  canInsert,
  onInsert,
}: {
  items: MarketComparisonItemDto[]
  /** Trägt die Gesamtabdeckung eine Antragsaussage? (marketUiState) */
  canInsert: boolean
  onInsert: (text: string) => void
}) {
  const insertableOf = (item: MarketComparisonItemDto) =>
    canInsert &&
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
                  <p className="text-xs text-muted-foreground">{ITEM_CATEGORY_LABELS[item.category]}</p>
                </td>
                <td className="py-2 pr-3 leading-relaxed text-muted-foreground">{item.differentiation_relevance?.trim() || "—"}</td>
                <td className="py-2 pr-3">
                  {item.evidence_quotes.length > 0 ? (
                    <blockquote className="border-l-2 border-border pl-2 text-xs italic leading-relaxed text-muted-foreground">
                      „{item.evidence_quotes[0].quote}“
                    </blockquote>
                  ) : (
                    <span className="text-xs text-muted-foreground">Kein belegtes Zitat</span>
                  )}
                </td>
                <td className="py-2 pr-3">
                  <Badge variant="secondary" className={CONFIDENCE_STYLE[item.confidence_label]}>
                    {CONFIDENCE_LABELS[item.confidence_label]}
                  </Badge>
                  {item.status !== "proposed" && (
                    <span className="mt-1 block text-xs text-muted-foreground">{ITEM_STATUS_LABELS[item.status]}</span>
                  )}
                </td>
                <td className="py-2">
                  {insertable && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onInsert(`Abgrenzung zu ${item.name}: ${item.differentiation_relevance?.trim() ?? ""}`)}
                    >
                      Als Argument übernehmen
                    </Button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
